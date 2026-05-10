"""
LLM service - integrates with Gemini 2.0 Flash API.
Handles prompting, parsing, error handling, retries, timeouts, and rate limiting.
"""

import json
from typing import Dict, Optional, List
import time
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.config import settings
from app.logger_config.logger import get_logger

logger = get_logger("llm_service")


class LLMService:
    """
    Service for LLM calls to Gemini 2.0 Flash.
    Handles structured output, retries, timeouts, rate limiting, and error handling.
    """

    def __init__(self):
        """Initialize Gemini client."""
        self.disabled = not bool(settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here")
        if self.disabled:
            logger.warning("Gemini API key not configured; LLM service is running in disabled mode")
            self.model = settings.gemini_model
            self.max_retries = 0
            self.retry_delay = 0.0
            self.timeout = settings.gemini_timeout_seconds
            self.generation_config = {
                "temperature": settings.gemini_temperature,
                "top_p": settings.gemini_top_p,
                "max_output_tokens": settings.gemini_max_tokens,
            }
            return

        genai.configure(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model
        self.max_retries = 3
        self.retry_delay = 1.0
        self.timeout = settings.gemini_timeout_seconds
        self.generation_config = {
            "temperature": settings.gemini_temperature,
            "top_p": settings.gemini_top_p,
            "max_output_tokens": settings.gemini_max_tokens,
        }

    def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict:
        """
        Generate response from Gemini with retry logic, timeouts, and rate limiting.

        Returns:
            Parsed response dict with reply, recommendations, end_of_conversation
        """

        if getattr(self, "disabled", False):
            return self._get_safe_default(has_recommendations=False)

        if conversation_context:
            system_prompt += f"\n\nCONTEXT:\n{conversation_context}"

        full_prompt = f"{system_prompt}\n\nUser: {user_message}"

        logger.debug(f"Calling Gemini with model={self.model}, max_tokens={max_tokens}")

        for attempt in range(self.max_retries):
            try:
                # Use the newer SDK style
                model = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config=self.generation_config
                )

                # Call Gemini
                response = model.generate_content(full_prompt, request_options={"timeout": 20})

                if response and response.text:
                    logger.debug(f"Gemini response (length={len(response.text)})")
                    result = self._parse_json_response(response.text)

                    if result:
                        logger.info("Successfully generated LLM response")
                        return result
                    else:
                        logger.warning(f"Failed to parse JSON, attempt {attempt + 1}/{self.max_retries}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay * (2 ** attempt))
                            continue

                return self._get_safe_default(has_recommendations=False)

            except google_exceptions.ResourceExhausted as e:
                # Rate limit hit
                wait_time = self.retry_delay * (2 ** (attempt + 1))
                logger.warning(f"Rate limited (429), waiting {wait_time}s before retry (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Rate limited after {self.max_retries} attempts")
                    return self._get_safe_default(has_recommendations=False)

            except (TimeoutError, google_exceptions.DeadlineExceeded) as e:
                logger.error(f"Timeout on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    return self._get_safe_default(has_recommendations=False)

            except google_exceptions.GoogleAPIError as e:
                logger.error(f"Gemini API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    return self._get_safe_default(has_recommendations=False)

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {type(e).__name__}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    return self._get_safe_default(has_recommendations=False)

        return self._get_safe_default(has_recommendations=False)

    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """
        Extract JSON from LLM response.
        LLM might return markdown code blocks or raw JSON.
        """

        text = text.strip()

        # Try markdown code block first
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        if text.startswith("```"):
            text = text[3:]  # Remove ```

        if text.endswith("```"):
            text = text[:-3]  # Remove trailing ```

        text = text.strip()

        try:
            data = json.loads(text)

            # Validate required fields
            if "reply" not in data or "recommendations" not in data or "end_of_conversation" not in data:
                logger.error("Missing required fields in response")
                return None

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            # Try to extract JSON manually
            import re

            # Look for {... } pattern
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass

            return None

    def _get_safe_default(self, has_recommendations: bool = False) -> Dict:
        """
        Return safe default response when parsing fails.
        
        CRITICAL: If we have recommendations from the ranking pipeline,
        don't show the fallback apology message - use a neutral success message instead.
        """
        if has_recommendations:
            # Ranking succeeded but LLM formatting failed - return neutral success
            return {
                "reply": "Here are the most relevant assessments based on your requirements:",
                "recommendations": [],  # Will be filled by caller
                "end_of_conversation": False,
                "_llm_failed": True,  # Flag for caller to know LLM failed
            }
        else:
            # True failure - no recommendations available
            return {
                "reply": "I couldn't generate recommendations at this moment. Please try again.",
                "recommendations": [],
                "end_of_conversation": False,
            }

    def generate_clarification(
        self, missing_info: List[str], context_str: str
    ) -> str:
        """Generate a clarification question using Gemini."""

        if getattr(self, "disabled", False):
            return "Could you clarify the role, seniority, and assessment focus?"

        prompt = f"""Generate ONE natural clarification question.

Missing information: {missing_info}
Current context: {context_str}

Question should be:
- Open-ended (not yes/no)
- Focused on the MOST important missing piece
- Conversational and friendly
- Short (1 sentence)

Just respond with the question, no explanation."""

        try:
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt, request_options={"timeout": 20})
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating clarification: {e}")
            return "Could you tell me more about the specific role and requirements?"

    def generate_comparison(
        self, assessment1_data: Dict, assessment2_data: Dict
    ) -> str:
        """Generate comparison between two assessments using Gemini."""

        from app.prompts.system_prompt import get_comparison_prompt

        prompt = get_comparison_prompt(
            assessment1_data.get("name", "Unknown"),
            assessment2_data.get("name", "Unknown"),
            {
                assessment1_data.get("name", "A"): assessment1_data,
                assessment2_data.get("name", "B"): assessment2_data,
            },
        )

        try:
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt, request_options={"timeout": 20})
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating comparison: {e}")
            return f"Both {assessment1_data.get('name')} and {assessment2_data.get('name')} assess important dimensions for this role."

    def generate_refusal(self, reason: str) -> str:
        """Generate a polite refusal message using Gemini."""

        from app.prompts.system_prompt import get_refuse_prompt

        prompt = get_refuse_prompt(reason)

        try:
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt, request_options={"timeout": 20})
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating refusal: {e}")
            return "I'm specifically designed to help with SHL assessment recommendations. How can I assist with your hiring needs?"

    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of tokens.
        Actual: ~1 token per 4 characters for English.
        """
        return len(text) // 4
