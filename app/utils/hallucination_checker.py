"""
Hallucination prevention and schema validation.
Ensures all recommendations are grounded in catalog.
"""

from typing import List, Dict, Optional
from app.models.assessment import AssessmentWithMetadata
from app.services.catalog_loader import CatalogLoader
from app.logging.logger import get_logger

logger = get_logger("safety")


class HallucinationChecker:
    """
    Detects and prevents hallucinations.
    Ensures all recommendations come from catalog only.
    """

    def __init__(self, catalog_loader: CatalogLoader):
        """Initialize with catalog."""
        self.catalog_loader = catalog_loader
        self._build_id_index()

    def _build_id_index(self) -> None:
        """Build index of valid assessment IDs and names."""
        self.valid_ids = set()
        self.valid_names = {}  # name -> id mapping
        self.valid_urls = {}   # url -> id mapping

        for assessment in self.catalog_loader.get_all():
            self.valid_ids.add(assessment.id)
            self.valid_names[assessment.name.lower()] = assessment.id
            self.valid_urls[assessment.url] = assessment.id

    def check_recommendations(self, recommendations: List[Dict]) -> tuple[bool, Optional[str]]:
        """
        Check if all recommendations are valid.

        Args:
            recommendations: List of {"name", "url", "test_type"}

        Returns:
            (is_valid, error_message)
        """

        if not recommendations:
            return True, None

        for i, rec in enumerate(recommendations):
            # Check name exists in catalog
            name = rec.get("name", "").lower()
            if name not in self.valid_names:
                return False, f"Recommendation {i+1}: Assessment '{rec.get('name')}' not found in catalog"

            # Check URL format
            url = rec.get("url", "")
            if not url.startswith("https://www.shl.com"):
                return False, f"Recommendation {i+1}: Invalid URL domain (must be shl.com)"

            # Check URL matches catalog
            catalog_assessment = self.catalog_loader.get_by_name(rec.get("name", ""))
            if catalog_assessment and url != catalog_assessment.url:
                return False, f"Recommendation {i+1}: URL doesn't match catalog"

            # Check test_type is valid
            test_type = rec.get("test_type", "")
            if test_type not in ["K", "A", "P"]:
                return False, f"Recommendation {i+1}: Invalid test_type '{test_type}'"

            # Verify test_type matches catalog
            if catalog_assessment and test_type != catalog_assessment.test_type.value:
                return False, f"Recommendation {i+1}: test_type mismatch with catalog"

        logger.info(f"Validation passed for {len(recommendations)} recommendations")
        return True, None

    def validate_comparison_items(self, items: List[str]) -> tuple[bool, Optional[str], Dict[str, AssessmentWithMetadata]]:
        """
        Validate comparison items exist in catalog.

        Args:
            items: List of assessment names to compare

        Returns:
            (is_valid, error_message, assessments_dict)
        """

        assessments = {}

        for item in items:
            item_lower = item.lower()

            # Try name match
            assessment = self.catalog_loader.get_by_name(item)

            if not assessment:
                # Try pattern matching
                for a in self.catalog_loader.get_all():
                    if item_lower in a.name.lower() or item_lower in a.id.lower():
                        assessment = a
                        break

            if not assessment:
                return False, f"Assessment '{item}' not found in catalog", {}

            assessments[item] = assessment

        logger.info(f"Validated {len(assessments)} comparison items")
        return True, None, assessments

    def prevent_hallucinations(self, text: str) -> tuple[bool, List[str]]:
        """
        Check if text contains hallucinated assessment references.

        Args:
            text: Generated text to check

        Returns:
            (is_clean, hallucinated_items)
        """

        hallucinated = []
        text_lower = text.lower()

        # Look for patterns like "X assessment" or "X test"
        import re

        patterns = [
            r"(\w+(?:\s+\w+)?)\s+(?:assessment|test|evaluation|screening)",
            r"(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:is a|measures|evaluates)",
        ]

        found_items = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text_lower):
                item = match.group(1).strip()
                found_items.add(item)

        # Check each found item against catalog
        for item in found_items:
            if item not in self.valid_names:
                # Only flag if it looks like an assessment name (contains key words)
                if any(word in item for word in ["test", "assessment", "evaluation"]):
                    continue  # Skip generic descriptions

                # Check if close to a catalog item
                is_close = any(
                    item in name or name in item
                    for name in [a.name.lower() for a in self.catalog_loader.get_all()]
                )

                if not is_close and len(item.split()) <= 3:
                    hallucinated.append(item)

        if hallucinated:
            logger.warning(f"Potential hallucinations detected: {hallucinated}")
            return False, hallucinated

        return True, []


class SchemaValidator:
    """Validates response schema compliance."""

    @staticmethod
    def validate_chat_response(response: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate ChatResponse schema.

        Required fields:
        - reply: str (non-empty)
        - recommendations: List (0 or 1-10 items)
        - end_of_conversation: bool
        """

        # Check all fields present
        if "reply" not in response:
            return False, "Missing 'reply' field"

        if "recommendations" not in response:
            return False, "Missing 'recommendations' field"

        if "end_of_conversation" not in response:
            return False, "Missing 'end_of_conversation' field"

        # Validate reply
        reply = response.get("reply")
        if not isinstance(reply, str):
            return False, "'reply' must be a string"

        if len(reply.strip()) == 0:
            return False, "'reply' cannot be empty"

        if len(reply) > 2000:
            return False, "'reply' exceeds max length (2000)"

        # Validate recommendations
        recs = response.get("recommendations")
        if not isinstance(recs, list):
            return False, "'recommendations' must be a list"

        if len(recs) > 10:
            return False, "Too many recommendations (max 10)"

        for i, rec in enumerate(recs):
            if not isinstance(rec, dict):
                return False, f"Recommendation {i+1} is not a dictionary"

            required = ["name", "url", "test_type"]
            for field in required:
                if field not in rec:
                    return False, f"Recommendation {i+1} missing '{field}'"

            # Check test_type value
            if rec.get("test_type") not in ["K", "A", "P"]:
                return False, f"Recommendation {i+1} has invalid test_type: {rec.get('test_type')}"

            # Check URL format
            url = rec.get("url", "")
            if not isinstance(url, str) or not url.startswith("https://www.shl.com"):
                return False, f"Recommendation {i+1} has invalid URL: {url}"

        # Validate end_of_conversation
        end_flag = response.get("end_of_conversation")
        if not isinstance(end_flag, bool):
            return False, "'end_of_conversation' must be a boolean"

        logger.info("Schema validation passed")
        return True, None

    @staticmethod
    def validate_request_schema(request_data: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate ChatRequest schema.

        Required:
        - messages: List of {"role": "user"/"assistant", "content": "..."}
        - Alternating user/assistant
        - Starts with user
        """

        if "messages" not in request_data:
            return False, "Missing 'messages' field"

        messages = request_data.get("messages")
        if not isinstance(messages, list):
            return False, "'messages' must be a list"

        if len(messages) == 0:
            return False, "'messages' cannot be empty"

        if len(messages) > 16:
            return False, "Too many messages (max 16)"

        # Check alternating roles
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                return False, f"Message {i+1}: must be an object"

            if "role" not in msg or "content" not in msg:
                return False, f"Message {i+1}: missing 'role' or 'content'"

            if msg["role"] not in ["user", "assistant"]:
                return False, f"Message {i+1}: 'role' must be 'user' or 'assistant'"

            # Check alternation
            if i > 0 and messages[i]["role"] == messages[i-1]["role"]:
                return False, f"Message {i+1}: roles must alternate"

            # First message must be from user
            if i == 0 and msg["role"] != "user":
                return False, "First message must be from user"

        logger.info("Request schema validation passed")
        return True, None
