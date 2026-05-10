"""
Conversation analyzer - extracts hiring context from messages.
Reconstructs conversation state to understand user needs.
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple, Dict
import re
from enum import Enum
from app.logger_config.logger import get_logger

logger = get_logger("conversation_analyzer")


class UserIntent(str, Enum):
    """Detected user intent."""
    VAGUE_QUERY = "vague"
    CLARIFICATION_PROVIDED = "clarification"
    REFINEMENT = "refinement"
    COMPARISON = "comparison"
    OFF_TOPIC = "off_topic"
    PROMPT_INJECTION = "prompt_injection"
    CLEAR_REQUIREMENT = "clear_requirement"


@dataclass
class HiringContext:
    """
    Extracted hiring context from conversation.
    Stateless reconstruction container.
    """
    role: Optional[str] = None
    tech_stack: Set[str] = field(default_factory=set)
    domain: Optional[str] = None
    seniority: Optional[str] = None
    soft_skills: Set[str] = field(default_factory=set)
    technical_skills: Set[str] = field(default_factory=set)
    leadership_needs: bool = False
    workflow_mode: str = "detailed"
    refinement_filters: Set[str] = field(default_factory=set)
    preferred_test_types: Set[str] = field(default_factory=set)

    def get_missing_info(self) -> List[str]:
        missing = []
        if not (self.role or self.domain): missing.append("role")
        if not self.seniority: missing.append("seniority")
        if not (self.soft_skills or self.technical_skills or self.tech_stack or self.preferred_test_types):
            missing.append("skills")
        return missing

    def is_sufficient(self) -> bool:
        """Check if enough context for a recommendation (Phase 3)."""
        # Strict threshold for enterprise copilot
        # 1. Role is mandatory
        if not (self.role or self.domain):
            return False
            
        # 2. Must have at least ONE specificity signal (Seniority, Skills, or Tech Stack)
        has_spec = bool(self.seniority) or bool(self.soft_skills) or bool(self.tech_stack) or bool(self.preferred_test_types) or self.leadership_needs
        
        # 3. Domain-specific sufficiency
        role_text = f"{self.role or ''} {self.domain or ''}".lower()
        
        # Tech roles need tech stack OR seniority
        clear_tech_signals = ["java", "python", "react", "data scientist", "machine learning", "sql", "devops", "cloud engineer"]
        if any(signal in role_text for signal in clear_tech_signals):
            return bool(self.tech_stack or self.seniority)

        # Broad roles (Sales/Support/HR) need BOTH seniority AND skill focus
        broad_signals = ["sales", "support", "operations", "leadership", "finance", "graduate", "assistant", "marketing"]
        if any(signal in role_text for signal in broad_signals):
            return bool(self.seniority) and bool(self.soft_skills or self.technical_skills or self.tech_stack)

        has_role = bool(self.role or self.domain)
        return has_role and has_spec

    def get_completeness_score(self) -> float:
        """Calculate a 0.0-1.0 score for context completeness."""
        score = 0.0
        if self.role or self.domain: score += 0.4
        if self.seniority: score += 0.2
        if self.tech_stack or self.soft_skills: score += 0.2
        if self.preferred_test_types or self.leadership_needs: score += 0.2
        return score

    def __str__(self) -> str:
        parts = []
        if self.role: parts.append(f"Role: {self.role}")
        if self.tech_stack: parts.append(f"Tech: {', '.join(self.tech_stack)}")
        if self.seniority: parts.append(f"Level: {self.seniority}")
        return " | ".join(parts) if parts else "No context"


class ConversationAnalyzer:
    """Analyzes conversations to extract hiring context."""

    SENIORITY_KEYWORDS = {
        "junior": ["junior", "entry-level", "fresh", "graduate", "entry level", "entrylevel"],
        "mid": ["mid-level", "intermediate", "mid level", "mid-level", "3-5 years"],
        "senior": ["senior", "staff", "principal", "lead", "experienced", "10+ years"],
        "executive": ["executive", "vp", "director", "head of", "cxo", "chief"]
    }

    TECH_KEYWORDS = {
        "java", "spring", "j2ee", "hibernate", 
        "python", "django", "flask", "asyncio", "scikit-learn", "tensorflow", "pytorch",
        "javascript", "typescript", "react", "angular", "vue", "frontend", "ui", "client-side",
        "go", "golang", "sql", "postgres", "nosql", "mongodb",
        "aws", "azure", "gcp", "docker", "kubernetes", "devops", "cicd", "terraform",
        "machine learning", "ml", "ai", "data science", "analytics", "nlp", "computer vision"
    }
    BUSINESS_KEYWORDS = {
        "sales": ["sales", "account executive", "business development", "sdr", "bdr", "quota", "persuasion"],
        "marketing": ["marketing", "growth", "campaign", "seo", "branding"],
        "finance": ["finance", "accounting", "audit", "tax", "banking"],
        "operations": ["operations", "logistics", "supply chain", "process"],
        "hr": ["hr", "recruiting", "talent acquisition", "human resources"],
        "product": ["product management", "product owner", "product manager"],
        "support": ["customer support", "support", "service desk", "customer care"]
    }
    SOFT_SKILL_KEYWORDS = {
        "communication", "empathy", "judgment", "stakeholder", "leadership", "execution",
        "organization", "analytical", "problem solving", "learning agility", "persuasion",
        "collaboration", "customer service", "attention to detail", "coordination", "adaptability",
        "relationship building", "conflict resolution", "prioritization", "influence", "decision making",
    }

    def __init__(self):
        self.SENIORITY_KEYWORDS_REVERSE = {}
        for level, keywords in self.SENIORITY_KEYWORDS.items():
            for keyword in keywords:
                self.SENIORITY_KEYWORDS_REVERSE[keyword] = level

    def analyze_conversation(self, messages: List[dict]) -> Tuple[HiringContext, UserIntent]:
        """Statelessly reconstruct context with query isolation (Part 2)."""
        context = HiringContext()
        user_messages = [m["content"] for m in messages if m["role"] == "user"]
        if not user_messages: return context, UserIntent.VAGUE_QUERY

        latest_user_msg = user_messages[-1]
        
        # 1. Determine the 'Request Boundary'
        # Find the last message that was a completely new hiring request
        boundary_idx = 0
        temp_ctx = HiringContext()
        for i, msg in enumerate(user_messages):
            if i > 0 and self.is_new_hiring_request(msg, temp_ctx):
                boundary_idx = i
                temp_ctx = HiringContext() # Reset temp for detection
            self._extract_context(msg, temp_ctx)
            
        # 2. Only process messages FROM the boundary to avoid contamination
        active_messages = user_messages[boundary_idx:]
        logger.info(f"Query isolation: Processing {len(active_messages)} messages from boundary index {boundary_idx}")
        
        for user_msg in active_messages:
            self._extract_context(user_msg, context)

        intent = self._detect_intent(latest_user_msg, len(user_messages), context)
        
        # 3. Refinement Check: if it's not a new request but has role context, it's a refinement
        if boundary_idx == len(user_messages) - 1 and len(user_messages) > 1:
            # This was a new request, intent should be CLEAR_REQUIREMENT if sufficient
            pass 

        # Heuristic for clarification merge
        if len(latest_user_msg.split()) <= 2 and intent == UserIntent.VAGUE_QUERY:
             intent = UserIntent.CLARIFICATION_PROVIDED

        return context, intent

    def is_new_hiring_request(self, message: str, current_context: HiringContext) -> bool:
        """
        Identify if the user is switching to a completely new role (Part 4).
        """
        msg_low = message.lower()
        
        # 1. Explicit transition markers
        transitions = ["instead", "another role", "different position", "now hiring", "for a different", "switch to", "new request"]
        if any(t in msg_low for t in transitions):
            return True
            
        # 2. New role/domain markers for specific keywords
        new_tech = ["for java", "for python", "for react", "for sales", "for marketing", "for support"]
        if any(t in msg_low for t in new_tech):
            return True

        # 3. Significant role change detection
        # Extract role from THIS message only
        temp_context = HiringContext()
        self._extract_context(message, temp_context)
        
        if temp_context.role and current_context.role:
            if temp_context.role.lower() != current_context.role.lower():
                # Avoid resetting for refinements like "senior java" vs "java"
                if temp_context.role.lower() not in current_context.role.lower() and current_context.role.lower() not in temp_context.role.lower():
                    logger.info(f"New hiring request detected: {current_context.role} -> {temp_context.role}")
                    return True
                    
        if temp_context.domain and current_context.domain and temp_context.domain != current_context.domain:
             return True
             
        return False

    def _detect_intent(self, latest_message: str, message_count: int, context: HiringContext) -> UserIntent:
        msg_lower = latest_message.lower()
        if self._is_off_topic(msg_lower): return UserIntent.OFF_TOPIC
        if self._is_prompt_injection(msg_lower): return UserIntent.PROMPT_INJECTION

        if any(p in msg_lower for p in ["compare", "vs ", "versus", "difference between"]):
            return UserIntent.COMPARISON

        if any(p in msg_lower for p in ["also add", "additionally", "actually", "more"]) and message_count > 1:
            return UserIntent.REFINEMENT

        if not context.role and not context.domain:
            if any(term in msg_lower for term in ["developer", "engineer", "specialist", "test for"]):
                return UserIntent.VAGUE_QUERY

        return UserIntent.CLEAR_REQUIREMENT

    def _is_off_topic(self, text: str) -> bool:
        """Phase 6: Strict off-topic refusal."""
        off_topic_patterns = [
            "joke", "weather", "movie", "music", "politics", "python tutorial",
            "how to code", "coding help", "write code", "debug", "salary", "market rate",
            "legal advice", "teach me", "restaurants", "who are you", "what can you do",
            "prompt injection", "hello", "hi "
        ]
        for pattern in off_topic_patterns:
            if re.search(rf"\b{re.escape(pattern)}\b", text):
                # Exception: greetings are okay if followed by relevant content in same message
                if pattern in ["hello", "hi"] and len(text.split()) > 5: continue
                return True
        return False

    def _is_prompt_injection(self, text: str) -> bool:
        return any(p in text for p in ["forget everything", "ignore", "system prompt", "jailbreak"])

    def _extract_context(self, message: str, context: HiringContext) -> None:
        msg_lower = message.lower()

        # 1. Seniority
        for kw, level in self.SENIORITY_KEYWORDS_REVERSE.items():
            if re.search(rf"\b{re.escape(kw)}\b", msg_lower):
                context.seniority = level
                break

        # 2. Role
        role_patterns = [
            r"for (?:a|an)?\s+([^,\.!?]+?)(?:\s+role|\s+position|$)",
            r"hiring (?:a|an)?\s+([^,\.!?]+)",
            r"test for (?:a|an)?\s+([^,\.!?]+)",
            r"need (?:a|an|some)?\s+([^,\.!?]+?)(?:\s+assessments?|\s+tests?|\s+screening|$)",
        ]
        for p in role_patterns:
            m = re.search(p, msg_lower)
            if m:
                role = m.group(1).strip()
                # Remove common noise words
                role = re.sub(r'^(?:a|an|the|some|assessments? for|tests? for)\s+', '', role)
                
                # If role is too long, it might contain skills; try to truncate at "with" or "and"
                if len(role.split()) >= 5:
                    role = re.split(r'\s+(?:with|and|who|for)\s+', role)[0].strip()
                
                # Clean up residual noise
                role = role.replace("assessments", "").replace("tests", "").strip()

                if role and len(role.split()) < 5: 
                    context.role = role
                    break

        # 3. Keywords
        for tech in self.TECH_KEYWORDS:
            if tech in msg_lower: 
                context.tech_stack.add(tech)
                # Assign specific domain and default role if it's a strong indicator
                if tech in ["java", "spring", "hibernate"]: 
                    context.domain = "java"
                    context.role = context.role or "Java Developer"
                elif tech in ["python", "django", "flask"]: 
                    context.domain = "python"
                    context.role = context.role or "Python Developer"
                elif tech in ["react", "angular", "frontend"]: 
                    context.domain = "frontend"
                    context.role = context.role or "Frontend Engineer"
                elif tech in ["machine learning", "data science", "ml"]: 
                    context.domain = "data_science"
                    context.role = context.role or "Data Scientist"
                elif tech in ["docker", "kubernetes", "devops"]: 
                    context.domain = "devops"
                    context.role = context.role or "DevOps Engineer"

        for domain, keywords in self.BUSINESS_KEYWORDS.items():
            # If domain is a dict key, check its keywords
            if isinstance(keywords, list):
                if any(kw in msg_lower for kw in keywords) or domain in msg_lower:
                    context.domain = domain
                    context.role = context.role or domain
            elif domain in msg_lower:
                context.domain = domain
                context.role = context.role or domain

        if "leadership" in msg_lower or "manager" in msg_lower or "executive" in msg_lower:
            context.leadership_needs = True
            context.domain = context.domain or "leadership"

        if "sales" in msg_lower:
            context.domain = "sales"
        elif "support" in msg_lower:
            context.domain = "support"

        for skill in self.SOFT_SKILL_KEYWORDS:
            if skill in msg_lower:
                context.soft_skills.add(skill)

        if any(keyword in msg_lower for keyword in ["technical", "coding", "software"]):
            context.preferred_test_types.update({"K", "A"})

        if any(keyword in msg_lower for keyword in ["behavioral", "personality", "soft skill", "culture fit"]):
            context.preferred_test_types.add("P")

        if any(keyword in msg_lower for keyword in ["reasoning", "aptitude", "cognitive", "analytical", "logic"]):
            context.preferred_test_types.add("A")

        if any(keyword in msg_lower for keyword in ["sales", "customer support", "support", "finance", "operations"]):
            context.preferred_test_types.update({"P", "A"})

    def get_clarification_question(self, context: HiringContext) -> Optional[str]:
        """Intelligent Recruiter-Grade follow-up questions (Part 8)."""
        missing = context.get_missing_info()
        if not missing: return None

        role_text = (context.role or context.domain or "role").lower()
        
        # 1. SPECIFIC TECH CLARIFICATIONS
        if "java" in role_text or "python" in role_text or "react" in role_text:
            if not context.seniority:
                return f"What seniority level are you targeting for this {role_text} role (e.g., Junior, Senior, or Staff)?"
            if not context.tech_stack:
                return f"Are there specific frameworks or libraries (like Spring, Django, or Redux) required for this {role_text} position?"

        # 2. BUSINESS DOMAIN CLARIFICATIONS
        if "sales" in role_text:
            if not context.seniority:
                 return "Is this for an entry-level SDR role, an experienced Account Executive, or a Sales Leadership position?"
            return "Should I prioritize personality traits like persuasion and resilience, or communication and negotiation skills?"

        if "support" in role_text or "customer" in role_text:
            return "Is this for a front-line customer care role or a technical service desk position? Also, what experience level are you looking for?"

        if "leadership" in role_text or "manager" in role_text:
            return "Is this for a people manager role or an executive leadership position? Should the focus be on strategic management or operational execution?"

        # 3. GENERIC BUT INTELLIGENT FALLBACKS
        if "role" in missing:
            return "What specific role are you hiring for today?"
            
        if "seniority" in missing:
            return f"What seniority level or years of experience are you targeting for the {role_text} position?"
            
        if "skills" in missing:
            return f"To provide the best match for this {role_text} role, should I prioritize technical skills, cognitive ability, or behavioral fit?"

        return "Could you provide a few more details about the role and the ideal candidate profile?"
