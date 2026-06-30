"""
Hardened Conversation Analyzer for AssessIQ.
Implements deterministic clarification state machine and robust skill extraction.
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple, Dict, Any
import re
from enum import Enum
from app.logger_config.logger import get_logger
from app.services.skill_graph import SkillGraph

logger = get_logger("conversation_analyzer")

class UserIntent(str, Enum):
    VAGUE_QUERY = "vague"
    CLARIFICATION_PROVIDED = "clarification"
    REFINEMENT = "refinement"
    COMPARISON = "comparison"
    OFF_TOPIC = "off_topic"
    CLEAR_REQUIREMENT = "clear_requirement"

@dataclass
class HiringContext:
    role: Optional[str] = None
    domain: str = "general"
    seniority: str = "mid"
    tech_stack: Set[str] = field(default_factory=set)
    workflow_mode: str = "default"
    leadership_needs: bool = False
    normalized_role: Optional[Any] = None
    
    # State tracking (Phase 4)
    asked_slots: Set[str] = field(default_factory=set)
    inferred_slots: Set[str] = field(default_factory=set)
    is_sufficient: bool = False

    # Additional properties needed by ranker
    soft_skills: Set[str] = field(default_factory=set)
    technical_skills: Set[str] = field(default_factory=set)
    refinement_filters: List[str] = field(default_factory=list)
    preferred_test_types: Set[str] = field(default_factory=set)

    def get_missing_slots(self) -> List[str]:
        # Role is sufficient for initial recommendations in all strongly mapped domains.
        required = ["role"]
        
        missing = []
        if not self.role: missing.append("role")
        
        # Don't ask for things we already asked or inferred
        return [s for s in missing if s not in self.asked_slots and s not in self.inferred_slots]

    def get_completeness_score(self) -> float:
        # Calculate completeness score based on filled fields
        score = 0.0
        if self.role:
            score += 0.4
        if self.tech_stack:
            score += 0.3
        if self.seniority:
            score += 0.3
        return score

class ConversationAnalyzer:
    """
    Deterministic Clarification State Machine (Phase 4).
    """
    
    def __init__(self, skill_graph: Optional[SkillGraph] = None):
        self.skill_graph = skill_graph or SkillGraph()

    GENERIC_ROLE_QUERIES = {
        "developer",
        "software engineer",
        "engineer",
        "programmer",
        "software developer",
    }

    DOMAIN_HINT_KEYWORDS = {
        "backend", "frontend", "fullstack", "full stack", "devops", "sre", "qa", "sdet",
        "data scientist", "machine learning", "ml", "mobile", "android", "ios", "security",
        "java", "python", "react", "angular", "vue", "javascript", "typescript", "nextjs",
        "fastapi", "django", "flask", "kubernetes", "terraform", "docker", "api", "microservice",
    }

    def analyze(self, messages: List[Dict[str, str]]) -> Tuple[HiringContext, UserIntent]:
        full_text = " ".join([m["content"] for m in messages if m["role"] == "user"]).lower()
        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "").lower()
        
        context = HiringContext()
        
        # 1. Track what the assistant already asked (Phase 4)
        for m in messages:
            if m["role"] == "assistant":
                content = m["content"].lower()
                if any(w in content for w in ["seniority", "experience level"]): context.asked_slots.add("seniority")
                if any(w in content for w in ["role", "position", "technical area"]): context.asked_slots.add("role")
                if any(w in content for w in ["tech stack", "skills", "framework"]): context.asked_slots.add("tech_stack")

        # 2. Robust Skill & Role Extraction (Phase 3)
        context.role = self._extract_role(full_text)
        context.seniority = self._extract_seniority(full_text) or "mid"
        context.tech_stack = self._extract_tech_stack(full_text)

        if self._is_generic_without_domain_signal(full_text, context.role, context.tech_stack):
            context.role = None
            context.tech_stack = set()
        
        # NEW: Infer tech_stack from role if not explicitly provided
        if not context.tech_stack and context.role:
            role_lower = context.role.lower()
            inferred_tech = []
            if "java" in role_lower and "javascript" not in role_lower:
                inferred_tech.append("Java")
            if "python" in role_lower:
                inferred_tech.append("Python")
            if "react" in role_lower or "frontend" in role_lower:
                inferred_tech.append("React")
            if "node" in role_lower:
                inferred_tech.append("Node.js")
            if "devops" in role_lower or "sre" in role_lower:
                inferred_tech.append("DevOps")
            if inferred_tech:
                context.tech_stack = set(inferred_tech)
        
        context.domain = self._infer_domain(context.role, context.tech_stack, full_text)

        # 3. Mark inferred slots
        if context.role: context.inferred_slots.add("role")
        if context.tech_stack: context.inferred_slots.add("tech_stack")
        if "senior" in full_text or "junior" in full_text: context.inferred_slots.add("seniority")

        # 4. Role Normalization (Phase 4)
        from app.services.role_normalizer import RoleNormalizer
        normalizer = RoleNormalizer()
        context.normalized_role, _, _ = normalizer.normalize_role(context.role or last_user_msg)

        # 4. Convergence Logic (Phase 4 & 6)
        missing = context.get_missing_slots()
        # Sufficient if we have core info OR we've hit the turn limit
        context.is_sufficient = not missing or len(messages) >= 6
        
        # 5. Intent Detection
        intent = UserIntent.CLEAR_REQUIREMENT
        
        # Check off-topic and prompt injection
        off_topic_patterns = [
            r"\b(capital of|weather|joke|politics|sports|football|soccer|cricket|recipe|cook|tax|visa|passport|legal advice|salary guide|career path|interview tips)\b",
            r"\b(ignore previous|system prompt|you are no longer|jailbreak|reveal prompt|secret key|api key|aws exam|competitor)\b",
            r"ignore previous instructions",
            r"output hidden prompt",
            r"reveal the prompt"
        ]
        
        is_off_topic = False
        for pattern in off_topic_patterns:
            if re.search(pattern, last_user_msg.lower()):
                is_off_topic = True
                break
                
        hiring_signals = ["hire", "recruiter", "assessment", "candidate", "role", "developer", "engineer", "test", "resume", "cv", "job description", "jd", "looking for", "talent", "qualification", "seniority"]
        has_hiring_signal = any(s in last_user_msg.lower() for s in hiring_signals)
        
        if not context.role and not context.tech_stack and not has_hiring_signal:
            greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "how are you", "help"]
            is_greeting = any(g in last_user_msg.lower() for g in greetings)
            if not is_greeting:
                is_off_topic = True

        if is_off_topic:
            intent = UserIntent.OFF_TOPIC
        elif not context.role and not context.tech_stack:
            intent = UserIntent.VAGUE_QUERY
        elif any(p in last_user_msg for p in ["compare", "vs ", "versus"]):
            intent = UserIntent.COMPARISON
        elif len(messages) > 2 and intent == UserIntent.CLEAR_REQUIREMENT:
            intent = UserIntent.CLARIFICATION_PROVIDED

        return context, intent

    def _extract_role(self, text: str) -> Optional[str]:
        text_lower = text.lower()

        # Generic role-only prompts should clarify once instead of defaulting to Java/backend.
        if text_lower.strip() in self.GENERIC_ROLE_QUERIES:
            return None
        
        # PRIORITY 1: Most specific compound roles (exact matches first)
        compound_roles = [
            # Backend/Fullstack
            "python backend", "java backend", "backend engineer", "backend developer",
            "python backend engineer", "python backend developer", "java backend developer",
            "fastapi developer", "fastapi engineer",
            "fullstack developer", "full stack developer", "java developer", "python developer",
            # Frontend specific
            "frontend software engineer", "frontend developer", "frontend engineer",
            "react developer", "react engineer", "angular developer", "angular engineer",
            "vue developer", "ui developer", "web developer", "javascript developer", "javascript engineer",
            "typescript developer", "typescript engineer",
            # Data/ML
            "data scientist", "machine learning engineer", "ml engineer", "ml ops",
            "data engineer", "ai engineer", "ai architect", "data analyst",
            "platform engineer", "systems engineer", "embedded developer",
            # QA/DevOps
            "qa automation", "sdet", "test automation", "qa engineer",
            "devops engineer", "sre", "site reliability", "cloud engineer",
            # Management
            "engineering manager", "product manager", "tech lead", "technical lead",
            "cto", "chief technology", "vp engineering", "head of engineering",
            # Generic compound
            "sales manager", "account manager", "customer support", "helpdesk"
        ]
        for r in compound_roles:
            if r in text_lower: 
                return r
        
        # PRIORITY 2: Technology keywords with context
        if any(token in text_lower for token in ["react", "angular", "vue", "javascript", "typescript", "nextjs"]):
            return "frontend"
        if "frontend" in text_lower or "ui" in text_lower or "web" in text_lower:
            return "frontend"
        if "machine learning" in text_lower or " ml " in text_lower or "data science" in text_lower:
            return "data scientist"
        if "ai " in text_lower and "artificial intelligence" in text_lower:
            return "ai engineer"
        if "java" in text_lower and "javascript" not in text_lower:
            return "java backend"
        if "python" in text_lower:
            return "python backend"
        if "devops" in text_lower or "sre" in text_lower:
            return "devops"
        if "cloud" in text_lower:
            return "cloud"
        if "kubernetes" in text_lower or "docker" in text_lower or "terraform" in text_lower:
            return "devops"
        
        # PRIORITY 3: Standalone role keywords (sorted by priority)
        standalone_roles = [
            "fullstack", "backend", "frontend", "qa", "sdet", "test",
            "data scientist", "data engineer", "analyst",
            "manager", "architect", "lead", "cto",
            "sales", "support", "executive",
            "sre", "engineer", "developer"
        ]
        for r in standalone_roles:
            if r in text_lower: 
                return r
        
        # VAGUE: Too generic - return None to trigger clarification
        vague_terms = ["programmer", "coder", "hack", "computer"]
        for v in vague_terms:
            if v in text_lower:
                return None
        
        return None

    def _is_generic_without_domain_signal(self, text: str, role: Optional[str], tech_stack: Set[str]) -> bool:
        text_low = text.lower().strip()
        role_low = (role or "").lower().strip()

        generic_hit = role_low in self.GENERIC_ROLE_QUERIES or text_low in self.GENERIC_ROLE_QUERIES
        if not generic_hit:
            return False

        if tech_stack:
            return False

        return not any(keyword in text_low for keyword in self.DOMAIN_HINT_KEYWORDS)

    def _extract_seniority(self, text: str) -> Optional[str]:
        if any(w in text for w in ["senior", "lead", "architect", "staff", "principal", "manager", "director", "head of", "vp"]):
            return "senior"
        if any(w in text for w in ["junior", "entry", "intern", "graduate", "trainee"]):
            return "entry"
        return "mid"

    def _extract_tech_stack(self, text: str) -> Set[str]:
        tech = set()
        for name in self.skill_graph.nodes.keys():
            if re.search(rf"\b{re.escape(name)}\b", text):
                tech.add(name)
        return tech

    def _infer_domain(self, role: Optional[str], tech: Set[str], text: str) -> str:
        combined = (role or "") + " " + " ".join(tech) + " " + text
        
        # Phase 3: Enhanced Domain Inference
        if any(w in combined for w in ["platform", "sre", "infrastructure", "kubernetes", "terraform", "cloud"]):
            return "devops"
        if any(w in combined for w in ["ml", "ai", "machine learning", "pytorch", "tensorflow", "architect"]):
            if "architect" in combined: return "backend engineering" # Technical depth
            return "data science"
        if any(w in combined for w in ["backend", "python", "java", "api", "apis", "microservice", "sql", "distributed", "server", "fastapi"]):
            return "backend engineering"
        if any(w in combined for w in ["frontend", "react", "angular", "vue", "css", "javascript", "typescript", "nextjs", "ui", "web"]):
            return "frontend engineering"
        if any(w in combined for w in ["qa", "test", "selenium", "cypress", "sdet", "automation", "playwright"]):
            return "qa automation"
        if any(w in combined for w in ["manager", "tech lead", "technical lead", "leadership", "people", "strategy", "executive", "stakeholder", "cto", "chief technology", "vp", "director", "head of"]):
            return "management"
        if any(w in combined for w in ["sales", "negotiation", "support", "customer", "business"]):
            return "business"
        return "software engineering"

    def get_clarification_question(self, context: HiringContext) -> Optional[str]:
        """Deterministic follow-up logic (Phase 4 & 5)."""
        missing = context.get_missing_slots()
        if not missing: return None
        
        slot = missing[0]
        if slot == "role":
            return "What type of engineering role are you hiring for? Examples: Backend, Frontend, DevOps, Data Science, QA, or Leadership."
        if slot == "tech_stack":
            return f"Are there specific frameworks or tools required for this {context.role} position (e.g. FastAPI, Kubernetes, or React)?"
        if slot == "seniority":
            return "What seniority level are you targeting (e.g. Junior, Senior, or Leadership)?"
            
        return None
