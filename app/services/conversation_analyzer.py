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

    def get_missing_slots(self) -> List[str]:
        required = ["role", "tech_stack"]
        # Some domains don't need explicit tech stack (like management, frontend, data science)
        if self.domain in ["management", "business", "frontend engineering", "data science", "qa"]:
            required = ["role"]
        
        missing = []
        if not self.role: missing.append("role")
        # Only backend engineering roles need explicit tech stack clarification
        if self.domain == "backend engineering" and not self.tech_stack: 
            missing.append("tech_stack")
        
        # Don't ask for things we already asked or inferred
        return [s for s in missing if s not in self.asked_slots and s not in self.inferred_slots]

class ConversationAnalyzer:
    """
    Deterministic Clarification State Machine (Phase 4).
    """
    
    def __init__(self, skill_graph: Optional[SkillGraph] = None):
        self.skill_graph = skill_graph or SkillGraph()

    def analyze(self, messages: List[Dict[str, str]]) -> Tuple[HiringContext, UserIntent]:
        full_text = " ".join([m["content"] for m in messages if m["role"] == "user"]).lower()
        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "").lower()
        
        context = HiringContext()
        
        # 1. Track what the assistant already asked (Phase 4)
        for m in messages:
            if m["role"] == "assistant":
                content = m["content"].lower()
                if any(w in content for w in ["seniority", "experience level"]): context.asked_slots.add("seniority")
                if any(w in content for w in ["role", "position"]): context.asked_slots.add("role")
                if any(w in content for w in ["tech stack", "skills", "framework"]): context.asked_slots.add("tech_stack")

        # 2. Robust Skill & Role Extraction (Phase 3)
        context.role = self._extract_role(full_text)
        context.seniority = self._extract_seniority(full_text) or "mid"
        context.tech_stack = self._extract_tech_stack(full_text)
        
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
                context.tech_stack = inferred_tech
        
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
        if not context.role and not context.tech_stack:
            intent = UserIntent.VAGUE_QUERY
        elif any(p in last_user_msg for p in ["compare", "vs ", "versus"]):
            intent = UserIntent.COMPARISON
        elif len(messages) > 2 and intent == UserIntent.CLEAR_REQUIREMENT:
            intent = UserIntent.CLARIFICATION_PROVIDED

        return context, intent

    def _extract_role(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        
        # PRIORITY 1: Most specific compound roles (exact matches first)
        compound_roles = [
            # Backend/Fullstack
            "python backend", "java backend", "backend engineer", "software engineer",
            "fullstack developer", "full stack developer", "java developer", "python developer",
            # Frontend specific
            "react developer", "angular developer", "vue developer", "frontend developer",
            "frontend engineer", "ui developer", "web developer",
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
        if "react" in text_lower or "angular" in text_lower or "vue" in text_lower:
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
        if any(w in combined for w in ["backend", "python", "java", "api", "microservice", "sql", "distributed", "server"]):
            return "backend engineering"
        if any(w in combined for w in ["frontend", "react", "angular", "css", "javascript", "ui"]):
            return "frontend engineering"
        if any(w in combined for w in ["qa", "test", "selenium", "cypress", "sdet", "automation", "playwright"]):
            return "qa automation"
        if any(w in combined for w in ["manager", "tech lead", "technical lead", "leadership", "people", "strategy", "executive", "stakeholder", "cto", "chief technology", "vp", "director", "head of"]):
            return "management"
        if any(w in combined for w in ["sales", "negotiation", "support", "customer", "business"]):
            return "business"
        return "software engineering"

    def get_clarification_question(self, context: HiringContext) -> Optional[str]:
        """Deterministic follow-up logic (Phase 4)."""
        missing = context.get_missing_slots()
        if not missing: return None
        
        slot = missing[0]
        if slot == "role":
            return "What specific role are you hiring for today (e.g. Python Backend, DevOps, or Sales)?"
        if slot == "tech_stack":
            return f"Are there specific frameworks or tools required for this {context.role} position (e.g. FastAPI, Kubernetes, or React)?"
        if slot == "seniority":
            return "What seniority level are you targeting (e.g. Junior, Senior, or Leadership)?"
            
        return None
