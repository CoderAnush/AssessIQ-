"""RequirementResolver service for AssessIQ.
Determines the set of required assessment categories based on hiring context and domain.
"""

from typing import Set, Any
from app.services.domain_classifier import Domain

class RequirementResolver:
    """Resolve required assessment categories based on job type and seniority.
    Data-driven mappings aligning with official GenAI requirements.
    """

    def resolve(self, query_domain: Domain, context: Any) -> Set[str]:
        required: Set[str] = set()

        # Extract normalized seniority/role cues
        seniority = getattr(context, "seniority", "mid") or "mid"
        seniority = seniority.lower()
        role = getattr(context, "role", "") or ""
        role = role.lower()

        # 1. Graduate/Entry level check (Graduate -> Ability + Learning + Behaviour)
        if seniority == "entry" or "graduate" in role or "graduate" in seniority:
            required.update({"cognitive", "learning", "behaviour"})
            return required

        # 2. Leadership/Management check (Leadership -> Personality + Leadership Reports)
        if query_domain == Domain.MANAGEMENT or "manager" in role or "lead" in role or "director" in role:
            required.update({"personality", "leadership_report"})
            return required

        # 3. Technical Roles (Backend/Frontend/DevOps/Data/QA)
        # Backend/Frontend -> Technical + Cognitive + Personality
        technical_domains = {
            Domain.BACKEND,
            Domain.FRONTEND,
            Domain.DEVOPS,
            Domain.DATA_AI,
            Domain.QA,
            Domain.ENGINEERING_CORE
        }
        if query_domain in technical_domains or any(d in role for d in ["engineer", "developer", "programmer", "sdet"]):
            required.update({"technical", "cognitive", "personality"})
            return required

        # 4. Fallback / General Roles
        required.update({"technical", "cognitive", "personality"})
        return required
