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
    PROMPT_INJECTION = "prompt_injection"
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
        missing = []
        if not self.role:
            missing.append("role")
        elif self.role.lower() in ConversationAnalyzer.GENERIC_ROLE_QUERIES:
            role_low = self.role.lower()
            if role_low in {"developer", "engineer", "software engineer", "software developer", "programmer"}:
                if "seniority" not in self.asked_slots and "seniority" not in self.inferred_slots:
                    missing.append("seniority")
                if not self.tech_stack and "role" not in self.asked_slots and role_low in {"developer", "programmer"}:
                    missing.append("role")

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
        "software", "programmer", "coder", "civil", "mechanical", "electrical", "chemical", "aeronautical", "aerospace", "design"
    }

    def analyze(self, messages: List[Dict[str, str]]) -> Tuple[HiringContext, UserIntent]:
        # Copy and clean typos in messages
        cleaned_messages = []
        typos = {
            "jvaa": "java",
            "sprng": "spring",
            "enginer": "engineer",
            "springboot": "spring boot",
        }
        for m in messages:
            content = m["content"]
            if m["role"] == "user":
                for typo, correction in typos.items():
                    content = re.sub(rf"\b{typo}\b", correction, content, flags=re.IGNORECASE)
            cleaned_messages.append({"role": m["role"], "content": content})

        full_text = " ".join([m["content"] for m in cleaned_messages if m["role"] == "user"]).lower()
        last_user_msg = next((m["content"] for m in reversed(cleaned_messages) if m["role"] == "user"), "").lower()
        
        context = HiringContext()
        
        # 1. Track what the assistant already asked (Phase 4)
        for m in cleaned_messages:
            if m["role"] == "assistant":
                content = m["content"].lower()
                if any(w in content for w in ["seniority", "experience level"]): context.asked_slots.add("seniority")
                if any(w in content for w in ["role", "position", "technical area"]): context.asked_slots.add("role")
                if any(w in content for w in ["tech stack", "skills", "framework"]): context.asked_slots.add("tech_stack")

        # Chronological Context Update (fixes conversational refinement overriding)
        for m in cleaned_messages:
            if m["role"] == "user":
                msg_text = m["content"].lower()
                
                # Check what was specified in this turn
                new_role = self._extract_role(msg_text)
                new_seniority = self._extract_seniority(msg_text)
                new_tech = self._extract_tech_stack(msg_text)
                
                # Update context role
                if new_role:
                    context.role = new_role
                
                # Update context seniority
                if new_seniority:
                    context.seniority = new_seniority
                
                # Detect change/refinement of tech stack
                turn_tokens = set(re.findall(r'\b[a-z0-9.]+\b', msg_text))
                
                # Java -> React / Frontend refinement (Scenario 22/23)
                if any(tok in turn_tokens for tok in ["react", "frontend", "angular", "vue", "javascript", "typescript", "redux"]):
                    context.tech_stack = {t for t in context.tech_stack if "java" not in t.lower() and "spring" not in t.lower() and "python" not in t.lower()}
                    if not new_role or "backend" in new_role.lower():
                        context.role = "frontend"
                        
                # React -> Java / Backend refinement
                if any(tok in turn_tokens for tok in ["java", "springboot", "spring", "python", "fastapi", "django"]):
                    context.tech_stack = {t for t in context.tech_stack if "react" not in t.lower() and "angular" not in t.lower() and "vue" not in t.lower() and "javascript" not in t.lower()}
                    if not new_role or "frontend" in new_role.lower():
                        context.role = "backend"
                
                # Accumulate tech stack
                if new_tech:
                    if "actually" in msg_text or "instead" in msg_text:
                        context.tech_stack = new_tech
                    else:
                        context.tech_stack.update(new_tech)

        # Ensure default seniority if not specified
        if not context.seniority:
            context.seniority = "mid"

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
        
        if any(w in full_text for w in ["leadership", "executive", "director", "cxo", "vp ", "chief"]):
            context.leadership_needs = True

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
            r"\b(capital of|weather|joke|politics|sports|football|soccer|cricket|recipe|cook|tax|visa|passport|legal advice|salary|salary guide|career path|interview tips|hackerrank|codility|leetcode)\b",
            r"\b(ignore\s+(all\s+)?previous|system prompt|you are no longer|jailbreak|reveal prompt|secret key|api key|aws exam|competitor)\b",
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"output hidden prompt",
            r"reveal the prompt",
            r"legally required",
            r"legal obligation",
            r"regulatory obligation",
            r"does this.*satisfy.*requirement",
            r"legal compliance questions",
        ]
        
        is_off_topic = False
        is_prompt_injection = False
        for pattern in off_topic_patterns:
            if re.search(pattern, last_user_msg.lower()):
                if "ignore" in pattern or "prompt" in pattern or "jailbreak" in pattern:
                    is_prompt_injection = True
                else:
                    is_off_topic = True
                break
                
        hiring_signals = [
            "hire", "hiring", "recruiter", "assessment", "assessments", "candidate",
            "role", "developer", "engineer", "test", "resume", "cv", "job description",
            "jd", "looking for", "talent", "qualification", "seniority", "screening",
            "contact centre", "contact center", "customer service", "trainee", "scheme",
            "battery", "analyst", "operator", "admin", "healthcare", "financial",
            "graduate", "management trainee", "plant", "facility", "agents", "inbound",
            "recommend", "shortlist", "we need", "solutions", "solution for",
            "executive", "leadership", "director", "cxo", "sales", "marketing", "hr",
            "devops", "security", "cyber", "full stack", "fullstack", "backend",
            "frontend", "data scientist", "machine learning", "verify", "scenarios", "opq",
            "drop the", "final list", "remove the", "add a", "trainee", "scheme", "battery",
            "cognitive", "personality", "situational", "graduate",
        ]
        has_hiring_signal = any(s in full_text for s in hiring_signals)
        has_prior_recommendations = any(
            m["role"] == "assistant" and "|" in m.get("content", "")
            for m in messages[:-1]
        )
        
        is_comparison = any(p in last_user_msg for p in ["compare", "vs ", "versus"])
        
        if not context.role and not context.tech_stack and not has_hiring_signal and not is_comparison and not has_prior_recommendations:
            greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "how are you", "help"]
            is_greeting = any(g in last_user_msg.lower() for g in greetings)
            if not is_greeting:
                is_off_topic = True

        if is_prompt_injection:
            intent = UserIntent.PROMPT_INJECTION
        elif is_off_topic:
            intent = UserIntent.OFF_TOPIC
        elif any(p in last_user_msg for p in ["legally required", "legal obligation", "legal compliance", "does this test satisfy", "does this satisfy"]):
            intent = UserIntent.OFF_TOPIC
        elif is_comparison:
            intent = UserIntent.COMPARISON
        elif not context.role and not context.tech_stack:
            intent = UserIntent.VAGUE_QUERY
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
            # Leadership / executive
            "senior leadership", "leadership", "chief executive", "cxo", "director-level",
            "engineering manager", "sales manager", "account manager",
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
            "sales manager", "account manager", "customer support", "helpdesk",
            "contact centre", "contact center", "call center", "call centre",
            "customer service agent", "financial analyst", "graduate financial analyst",
            "hr executive", "marketing manager", "plant operator", "healthcare admin",
            "graduate management trainee", "management trainee", "trainee scheme",
            "fresh graduate software engineer", "graduate software engineer",
            "software engineer", "electrical engineer", "mechanical design engineer",
            "mechanical engineer", "civil engineer", "chemical engineer",
        ]
        for r in compound_roles:
            if r in text_lower: 
                return r
        
        if "graduate" in text_lower and "software" in text_lower and "engineer" in text_lower:
            return "graduate software engineer"
        if "electrical" in text_lower and "engineer" in text_lower:
            return "electrical engineer"
        if "mechanical" in text_lower and "engineer" in text_lower:
            return "mechanical design engineer"
        if "graduate" in text_lower and ("trainee" in text_lower or "management" in text_lower or "scheme" in text_lower):
            return "graduate management trainee"
        if "graduate" in text_lower and ("financial" in text_lower or "analyst" in text_lower):
            return "graduate financial analyst"
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
        
        # Skip "test" when user means an SHL assessment, not a QA/test role.
        assessment_test_context = bool(
            re.search(r"\b(?:need|want|looking for|require)\s+(?:a|an|the)?\s*test\b", text_lower)
            or re.search(r"\btest\s+for\b", text_lower)
            or re.search(r"\bassessment\b", text_lower)
        )

        # PRIORITY 3: Standalone role keywords (word-boundary matched)
        standalone_roles = [
            "fullstack", "backend", "frontend", "qa", "sdet",
            "data scientist", "data engineer", "analyst",
            "manager", "architect", "lead", "cto", "leadership", "executive",
            "sales", "support", "executive",
            "sre", "engineer", "developer",
        ]
        if not assessment_test_context:
            standalone_roles.insert(5, "test")
        for r in standalone_roles:
            if re.search(rf"\b{re.escape(r)}\b", text_lower):
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
        if any(w in combined for w in ["contact centre", "contact center", "call center", "customer service", "call centre"]):
            return "business"
        if any(w in combined for w in ["financial analyst", "finance", "accounting", "financial"]):
            return "business"
        if any(w in combined for w in ["hr ", "human resources", "recruitment"]):
            return "management"
        if any(w in combined for w in ["marketing", "seo", "sem", "digital marketing"]):
            return "business"
        if any(w in combined for w in ["security", "cyber", "siem", "penetration"]):
            return "business"
        if any(w in combined for w in ["electrical", "mechanical", "plant operator", "chemical"]):
            return "engineering"
        return "software engineering"

    def get_clarification_question(self, context: HiringContext) -> Optional[str]:
        """Deterministic follow-up logic (Phase 4 & 5)."""
        missing = context.get_missing_slots()
        if not missing: return None
        
        slot = missing[0]
        if slot == "role":
            if any(w in (context.domain or "") for w in ["business"]) and any(
                w in (context.role or "").lower() for w in ["contact", "customer service", "call"]
            ):
                return "Before I shape the stack — what language are the calls in? That drives which spoken-language screen we use."
            if any(w in (context.seniority or "") for w in ["senior", "executive"]) or context.leadership_needs:
                return "Happy to help narrow that down. Who is this meant for — selection, development, or a specific leadership level?"
            return (
                "What type of role and seniority are you hiring for? "
                "Examples: Senior Backend Developer, Junior Frontend Engineer, or Leadership — "
                "and any technical focus (e.g. Java, React, DevOps)."
            )
        if slot == "tech_stack":
            return f"Are there specific frameworks or tools required for this {context.role} position (e.g. FastAPI, Kubernetes, or React)?"
        if slot == "seniority":
            return (
                "What seniority level and technical focus should I use "
                "(e.g. Junior, Senior, or Leadership — plus backend, frontend, or other technical area)?"
            )
            
        return None
