"""RequirementResolver service for AssessIQ.
Determines the set of required assessment categories based on hiring context and domain.
"""

from typing import Set, Any
from app.services.domain_classifier import Domain

class RequirementResolver:
    """Resolve required assessment categories based on job type and seniority.
    Data-driven mappings aligning with official GenAI requirements.
    """

    _SALES_ROLE_SIGNALS = (
        "sales manager",
        "sales executive",
        "b2b sales",
        "account manager",
        "business development",
    )

    _MANAGEMENT_ROLE_SIGNALS = (
        "engineering manager",
        "product manager",
        "tech lead",
        "technical lead",
        "director",
        "executive",
        "leadership",
        "cto",
        "chief technology",
        "chief technical",
        "vp engineering",
        "head of engineering",
    )

    def _is_true_management_role(self, query_domain: Domain, role: str, user_query: str = "") -> bool:
        combined = f"{role} {user_query}".lower()
        if query_domain == Domain.MANAGEMENT:
            if any(sig in combined for sig in self._SALES_ROLE_SIGNALS):
                return False
            return True
        if any(sig in combined for sig in self._SALES_ROLE_SIGNALS):
            return False
        return any(sig in combined for sig in self._MANAGEMENT_ROLE_SIGNALS)

    def resolve(self, query_domain: Domain, context: Any) -> Set[str]:
        required: Set[str] = set()

        seniority = getattr(context, "seniority", "mid") or "mid"
        seniority = seniority.lower()
        role = getattr(context, "role", "") or ""
        role = role.lower()
        user_query = getattr(context, "query", "") or ""

        if seniority == "entry" or "graduate" in role or "graduate" in seniority:
            required.update({"cognitive", "learning", "behaviour"})
            return required

        if self._is_true_management_role(query_domain, role, user_query):
            required.update({"personality", "leadership_report"})
            return required

        technical_domains = {
            Domain.BACKEND,
            Domain.FRONTEND,
            Domain.DEVOPS,
            Domain.DATA_AI,
            Domain.QA,
            Domain.ENGINEERING_CORE,
        }
        if query_domain in technical_domains or any(
            d in role for d in ["engineer", "developer", "programmer", "sdet"]
        ):
            required.update({"technical", "cognitive", "personality"})
            return required

        if query_domain == Domain.GENERAL and any(sig in f"{role} {user_query}".lower() for sig in self._SALES_ROLE_SIGNALS):
            required.update({"personality"})
            return required

        required.update({"technical", "cognitive", "personality"})
        return required
