"""
Role Normalization Engine - Maps recruiter prompts to canonical hiring domains.
Provides enterprise-grade role understanding with fuzzy matching and weighted aliases.
"""

from typing import Dict, Set, Optional, Tuple, List
from enum import Enum
import re
from difflib import SequenceMatcher
from app.logger_config.logger import get_logger

logger = get_logger("role_normalizer")


class NormalizedRole(str, Enum):
    """Canonical role taxonomy."""
    BACKEND_ENGINEER = "backend_engineer"
    FRONTEND_ENGINEER = "frontend_engineer"
    FULLSTACK_ENGINEER = "fullstack_engineer"
    DATA_SCIENTIST = "data_scientist"
    DATA_ANALYST = "data_analyst"
    DEVOPS_ENGINEER = "devops_engineer"
    CLOUD_ENGINEER = "cloud_engineer"
    QA_ENGINEER = "qa_engineer"
    MOBILE_DEVELOPER = "mobile_developer"
    ML_ENGINEER = "ml_engineer"
    CYBERSECURITY_ANALYST = "cybersecurity_analyst"
    SALES_REP = "sales_rep"
    SALES_MANAGER = "sales_manager"
    CUSTOMER_SUPPORT = "customer_support"
    PRODUCT_MANAGER = "product_manager"
    ENGINEERING_MANAGER = "engineering_manager"
    OPERATIONS_MANAGER = "operations_manager"
    MARKETING_MANAGER = "marketing_manager"
    HR_PROFESSIONAL = "hr_professional"
    EXECUTIVE_ASSISTANT = "executive_assistant"
    GRADUATE_TRAINEE = "graduate_trainee"
    EXECUTIVE = "executive"
    GENERAL = "general"


class RoleNormalizer:
    """Normalizes recruiter prompts to canonical roles and domains."""

    # Role mapping with weighted aliases
    ROLE_ALIASES: Dict[NormalizedRole, Dict[str, float]] = {
        NormalizedRole.BACKEND_ENGINEER: {
            "backend engineer": 1.0,
            "python backend": 0.95,
            "java backend": 0.95,
            "backend developer": 0.90,
            "server-side engineer": 0.85,
            "api developer": 0.80,
            "fastapi": 0.90,
            "backend": 0.75,
        },
        NormalizedRole.FRONTEND_ENGINEER: {
            "frontend engineer": 1.0,
            "react developer": 0.95,
            "javascript developer": 0.90,
            "frontend developer": 0.90,
            "ui engineer": 0.85,
            "web developer": 0.80,
            "client-side engineer": 0.80,
            "frontend": 0.75,
        },
        NormalizedRole.FULLSTACK_ENGINEER: {
            "fullstack engineer": 1.0,
            "full-stack developer": 1.0,
            "fullstack developer": 1.0,
            "full stack": 0.95,
            "full-stack engineer": 1.0,
        },
        NormalizedRole.DATA_SCIENTIST: {
            "data scientist": 1.0,
            "machine learning engineer": 0.90,
            "ml engineer": 0.90,
            "analytics engineer": 0.80,
            "data engineer": 0.75,
        },
        NormalizedRole.DATA_ANALYST: {
            "data analyst": 1.0,
            "business analyst": 0.80,
            "analytics": 0.75,
        },
        NormalizedRole.DEVOPS_ENGINEER: {
            "devops engineer": 1.0,
            "devops": 0.95,
            "site reliability engineer": 0.90,
            "sre": 0.85,
            "infrastructure engineer": 0.80,
        },
        NormalizedRole.CLOUD_ENGINEER: {
            "cloud engineer": 1.0,
            "cloud architect": 0.90,
            "aws engineer": 0.85,
            "azure engineer": 0.85,
            "gcp engineer": 0.85,
        },
        NormalizedRole.QA_ENGINEER: {
            "qa engineer": 1.0,
            "quality assurance engineer": 0.95,
            "test engineer": 0.90,
            "qa automation": 0.95,
            "qa automation engineer": 1.0,
            "automation engineer": 0.85,
            "qa": 0.70,
        },
        NormalizedRole.MOBILE_DEVELOPER: {
            "mobile developer": 1.0,
            "ios developer": 0.95,
            "android developer": 0.95,
            "mobile engineer": 0.90,
        },
        NormalizedRole.ML_ENGINEER: {
            "machine learning engineer": 1.0,
            "ml engineer": 0.95,
            "deep learning engineer": 0.90,
            "ai engineer": 0.85,
        },
        NormalizedRole.CYBERSECURITY_ANALYST: {
            "cybersecurity analyst": 1.0,
            "security engineer": 0.95,
            "security analyst": 0.90,
            "infosec": 0.85,
        },
        NormalizedRole.SALES_REP: {
            "sales representative": 1.0,
            "sales rep": 1.0,
            "account executive": 0.90,
            "sales executive": 0.85,
            "sales": 0.70,
            "business development": 0.75,
        },
        NormalizedRole.SALES_MANAGER: {
            "sales manager": 1.0,
            "sales director": 0.90,
            "sales leader": 0.80,
        },
        NormalizedRole.CUSTOMER_SUPPORT: {
            "customer support": 1.0,
            "support representative": 0.95,
            "customer service": 0.90,
            "support": 0.70,
            "customer care": 0.85,
            "technical support specialist": 0.90,
            "technical support": 0.85,
        },
        NormalizedRole.PRODUCT_MANAGER: {
            "product manager": 1.0,
            "pm": 0.80,
            "product owner": 0.90,
            "product lead": 0.85,
        },
        NormalizedRole.ENGINEERING_MANAGER: {
            "engineering manager": 1.0,
            "technical manager": 0.95,
            "tech lead": 0.85,
            "team lead": 0.80,
            "engineering lead": 0.90,
            "backend team": 0.75,
            "engineering team": 0.70,
        },
        NormalizedRole.OPERATIONS_MANAGER: {
            "operations manager": 1.0,
            "operations": 0.80,
            "ops manager": 0.90,
        },
        NormalizedRole.MARKETING_MANAGER: {
            "marketing manager": 1.0,
            "marketing": 0.80,
            "growth manager": 0.75,
        },
        NormalizedRole.HR_PROFESSIONAL: {
            "hr professional": 1.0,
            "hr manager": 0.95,
            "talent acquisition": 0.90,
            "recruiter": 0.85,
            "hr": 0.70,
        },
        NormalizedRole.EXECUTIVE_ASSISTANT: {
            "executive assistant": 1.0,
            "administrative assistant": 0.90,
            "assistant": 0.70,
        },
        NormalizedRole.GRADUATE_TRAINEE: {
            "graduate trainee": 1.0,
            "junior developer": 0.80,
            "entry-level": 0.75,
            "junior": 0.65,
            "graduate": 0.80,
            "trainee": 0.85,
            "apprentice": 0.80,
        },
        NormalizedRole.EXECUTIVE: {
            "executive": 0.90,
            "ceo": 0.95,
            "cto": 0.95,
            "cfo": 0.95,
            "vp": 0.90,
            "director": 0.85,
            "c-level": 0.95,
        },
    }

    # Tech stack to domain mapping
    TECH_TO_DOMAIN: Dict[str, List[NormalizedRole]] = {
        "python": [NormalizedRole.BACKEND_ENGINEER, NormalizedRole.DATA_SCIENTIST, NormalizedRole.ML_ENGINEER],
        "java": [NormalizedRole.BACKEND_ENGINEER],
        "react": [NormalizedRole.FRONTEND_ENGINEER, NormalizedRole.FULLSTACK_ENGINEER],
        "javascript": [NormalizedRole.FRONTEND_ENGINEER, NormalizedRole.FULLSTACK_ENGINEER],
        "typescript": [NormalizedRole.FRONTEND_ENGINEER, NormalizedRole.FULLSTACK_ENGINEER],
        "golang": [NormalizedRole.BACKEND_ENGINEER],
        "go": [NormalizedRole.BACKEND_ENGINEER],
        "rust": [NormalizedRole.BACKEND_ENGINEER],
        "aws": [NormalizedRole.DEVOPS_ENGINEER, NormalizedRole.CLOUD_ENGINEER],
        "azure": [NormalizedRole.DEVOPS_ENGINEER, NormalizedRole.CLOUD_ENGINEER],
        "gcp": [NormalizedRole.DEVOPS_ENGINEER, NormalizedRole.CLOUD_ENGINEER],
        "kubernetes": [NormalizedRole.DEVOPS_ENGINEER],
        "docker": [NormalizedRole.DEVOPS_ENGINEER],
        "sql": [NormalizedRole.DATA_SCIENTIST, NormalizedRole.DATA_ANALYST, NormalizedRole.BACKEND_ENGINEER],
        "machine learning": [NormalizedRole.DATA_SCIENTIST, NormalizedRole.ML_ENGINEER],
        "ml": [NormalizedRole.DATA_SCIENTIST, NormalizedRole.ML_ENGINEER],
        "ios": [NormalizedRole.MOBILE_DEVELOPER],
        "android": [NormalizedRole.MOBILE_DEVELOPER],
        "swift": [NormalizedRole.MOBILE_DEVELOPER],
        "kotlin": [NormalizedRole.MOBILE_DEVELOPER],
        "security": [NormalizedRole.CYBERSECURITY_ANALYST],
        "django": [NormalizedRole.BACKEND_ENGINEER],
        "flask": [NormalizedRole.BACKEND_ENGINEER],
        "spring": [NormalizedRole.BACKEND_ENGINEER],
        "nodejs": [NormalizedRole.BACKEND_ENGINEER, NormalizedRole.FULLSTACK_ENGINEER],
        "node": [NormalizedRole.BACKEND_ENGINEER, NormalizedRole.FULLSTACK_ENGINEER],
        "fastapi": [NormalizedRole.BACKEND_ENGINEER],
        "testing": [NormalizedRole.QA_ENGINEER],
        "automation": [NormalizedRole.QA_ENGINEER],
        "qa": [NormalizedRole.QA_ENGINEER],
        "sdet": [NormalizedRole.QA_ENGINEER],
        "selenium": [NormalizedRole.QA_ENGINEER],
    }

    # Seniority extraction patterns
    SENIORITY_PATTERNS = {
        "junior": [r"\bjunior\b", r"\bentry[- ]?level\b", r"\bfresh\b", r"\bgraduate\b"],
        "mid": [r"\bmid[- ]?level\b", r"\bintermediate\b", r"\b3-5\b", r"\b3-5 years\b"],
        "senior": [r"\bsenior\b", r"\bstaff\b", r"\b5\+\b", r"\b10\+\b", r"\bexperienced\b"],
        "executive": [r"\bdirector\b", r"\bvp\b", r"\bexecutive\b", r"\bc[a-z]o\b"],
    }

    # Skill extraction patterns
    TECHNICAL_SKILLS = {
        "backend", "frontend", "fullstack", "coding", "programming", "software",
        "database", "api", "microservices", "cloud", "infrastructure", "devops",
        "containerization", "deployment", "ci/cd", "testing", "automation", "qa",
        "machine learning", "data analysis", "analytics", "big data", "sdet", "selenium",
    }

    SOFT_SKILLS = {
        "leadership", "management", "communication", "collaboration", "teamwork",
        "customer service", "sales", "persuasion", "negotiation", "presentation",
        "strategic thinking", "problem solving", "analytical", "judgment",
        "decision making", "stakeholder management",
    }

    def __init__(self):
        self.inverse_aliases = self._build_inverse_aliases()

    def _build_inverse_aliases(self) -> Dict[str, NormalizedRole]:
        """Build lookup from alias to normalized role."""
        inverse = {}
        for role, aliases in self.ROLE_ALIASES.items():
            for alias in aliases.keys():
                inverse[alias.lower()] = role
        return inverse

    def normalize_role(
        self, user_prompt: str, extracted_role: Optional[str] = None
    ) -> Tuple[Optional[NormalizedRole], float, Dict[str, any]]:
        """
        Normalize a user prompt to a canonical role.

        Returns:
            (normalized_role, confidence, details_dict)
        """
        prompt_lower = user_prompt.lower()
        details = {"method": None, "candidates": []}

        # 1. DIRECT EXTRACTION FROM PARSED ROLE
        if extracted_role:
            role, score = self._match_role(extracted_role)
            if role and score >= 0.70:
                details["method"] = "parsed_role"
                return role, score, details

        # 2. REGEX ROLE EXTRACTION
        regex_role = self._extract_role_via_regex(prompt_lower)
        if regex_role:
            role, score = self._match_role(regex_role)
            if role and score >= 0.75:
                details["method"] = "regex_extraction"
                return role, score, details

        # 3. TECH STACK INFERENCE
        tech_domains = self._infer_role_from_tech(prompt_lower)
        if tech_domains:
            # Pick the most commonly referenced domain
            role = tech_domains[0]
            details["method"] = "tech_inference"
            return role, 0.80, details

        # 4. FUZZY MATCHING
        role, score = self._fuzzy_match_role(prompt_lower)
        if role and score >= 0.70:
            details["method"] = "fuzzy_match"
            return role, score, details

        # 5. FALLBACK - GENERIC
        return NormalizedRole.GENERAL, 0.5, {"method": "fallback"}

    def _extract_role_via_regex(self, text: str) -> Optional[str]:
        """Extract role name using regex patterns."""
        patterns = [
            r"for (?:a|an)?\s+([^,\.!?]+?)(?:\s+role|\s+position|\s+engineer|\s+developer|$)",
            r"hiring (?:a|an)?\s+([^,\.!?]+)",
            r"(?:backend|frontend|fullstack|java|python|react|data|devops|qa|mobile|security|sales|product|support|hr|marketing|operations)\s+([a-z\s]+?(?:engineer|developer|manager|representative|specialist|analyst))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _match_role(self, text: str) -> Tuple[Optional[NormalizedRole], float]:
        """Match text to a normalized role."""
        text_lower = text.lower().strip()

        # Check if it's a direct alias match
        if text_lower in self.inverse_aliases:
            return self.inverse_aliases[text_lower], 1.0

        # Check partial matches
        for role, aliases in self.ROLE_ALIASES.items():
            for alias, weight in aliases.items():
                if alias in text_lower or text_lower in alias:
                    return role, weight

        return None, 0.0

    def _infer_role_from_tech(self, text: str) -> List[NormalizedRole]:
        """Infer role from detected tech stack."""
        roles_by_freq = {}

        for tech, roles in self.TECH_TO_DOMAIN.items():
            if tech in text:
                for role in roles:
                    roles_by_freq[role] = roles_by_freq.get(role, 0) + 1

        if roles_by_freq:
            sorted_roles = sorted(roles_by_freq.items(), key=lambda x: x[1], reverse=True)
            return [role for role, _ in sorted_roles]

        return []

    def _fuzzy_match_role(self, text: str) -> Tuple[Optional[NormalizedRole], float]:
        """Fuzzy match text to closest role alias."""
        words = text.split()
        best_role = None
        best_score = 0.0

        for role, aliases in self.ROLE_ALIASES.items():
            for alias in aliases.keys():
                for word_combo in self._generate_word_combos(words):
                    ratio = SequenceMatcher(None, word_combo, alias).ratio()
                    if ratio > best_score and ratio >= 0.65:
                        best_score = ratio
                        best_role = role

        return best_role, best_score

    def _generate_word_combos(self, words: List[str]) -> List[str]:
        """Generate word combinations for fuzzy matching."""
        combos = []
        for i in range(len(words)):
            for j in range(i + 1, min(i + 4, len(words) + 1)):
                combos.append(" ".join(words[i:j]))
        return combos

    def extract_seniority(self, text: str) -> Optional[str]:
        """Extract seniority level from text."""
        text_lower = text.lower()

        for level, patterns in self.SENIORITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return level

        return None

    def extract_skills(self, text: str) -> Tuple[Set[str], Set[str]]:
        """Extract technical and soft skills."""
        text_lower = text.lower()
        technical = set()
        soft = set()

        for skill in self.TECHNICAL_SKILLS:
            if skill in text_lower:
                technical.add(skill)

        for skill in self.SOFT_SKILLS:
            if skill in text_lower:
                soft.add(skill)

        return technical, soft

    def extract_tech_stack(self, text: str) -> Set[str]:
        """Extract specific technologies."""
        text_lower = text.lower()
        techs = set()

        for tech in self.TECH_TO_DOMAIN.keys():
            if tech in text_lower:
                techs.add(tech)

        return techs

    def get_domain_keywords(self, role: NormalizedRole) -> Set[str]:
        """Get domain-specific keywords for retrieval."""
        keywords = set()

        # Add tech stack keywords
        for tech, roles in self.TECH_TO_DOMAIN.items():
            if role in roles:
                keywords.add(tech)

        # Add role aliases
        if role in self.ROLE_ALIASES:
            keywords.update(self.ROLE_ALIASES[role].keys())

        return keywords
