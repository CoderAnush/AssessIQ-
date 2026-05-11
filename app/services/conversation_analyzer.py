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
        # Tech roles need tech stack, management needs leadership signal
        if self.domain in ["management", "business"]:
            required = ["role"]
        
        missing = []
        if not self.role: missing.append("role")
        if self.domain == "backend engineering" and not self.tech_stack: missing.append("tech_stack")
        
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
        roles = [
            # Specific compound roles (longer first for priority)
            "python backend", "java backend", "backend engineer", "software engineer",
            "qa automation", "product manager", "engineering manager", 
            "data scientist", "ml engineer", "platform engineer", "ai architect",
            "systems engineer", "embedded developer", "data engineer",
            # Standalone keywords (shorter)
            "java", "python", "backend", "frontend", "fullstack", 
            "devops", "cloud", "qa", "sdet", "sales", 
            "customer support", "support", "executive", "architect", "manager",
            "sre", "engineer", "developer"
        ]
        # Sort by length to match longer specific roles first
        for r in sorted(roles, key=len, reverse=True):
            if r in text: return r
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
        if any(w in combined for w in ["manager", "lead", "leadership", "people", "strategy", "executive", "stakeholder"]):
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
