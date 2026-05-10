"""
Intelligent metadata enrichment for SHL assessments.
Infers additional metadata to improve retrieval and ranking.
"""

import logging
from typing import Dict, List, Set
from enum import Enum

logger = logging.getLogger(__name__)


class SkillCategory(str, Enum):
    """Skill categories for enrichment."""

    COMMUNICATION = "communication"
    LEADERSHIP = "leadership"
    PROBLEM_SOLVING = "problem_solving"
    TEAMWORK = "teamwork"
    DECISION_MAKING = "decision_making"
    REASONING = "reasoning"
    TECHNICAL = "technical"
    PERSONALITY = "personality"
    COGNITIVE = "cognitive"


class MetadataEnricher:
    """Enriches assessment metadata to improve retrieval quality."""

    # Knowledge bases for enrichment
    COMMUNICATION_KEYWORDS = {
        "communication",
        "interpersonal",
        "presentation",
        "negotiation",
        "influence",
        "articulation",
        "listening",
        "collaboration",
        "verbal",
    }

    LEADERSHIP_KEYWORDS = {
        "leadership",
        "management",
        "delegation",
        "strategic",
        "vision",
        "decision-making",
        "executive",
        "director",
        "manager",
    }

    TECHNICAL_KEYWORDS = {
        "technical",
        "programming",
        "coding",
        "java",
        "python",
        "sql",
        "database",
        "software",
        "engineering",
        "development",
        "it",
        "cybersecurity",
    }

    PERSONALITY_KEYWORDS = {
        "personality",
        "trait",
        "behavior",
        "profile",
        "style",
        "motivation",
        "preference",
        "otpq",
        "16pf",
        "opq",
    }

    COGNITIVE_KEYWORDS = {
        "cognitive",
        "reasoning",
        "problem-solving",
        "numerical",
        "verbal",
        "logic",
        "deductive",
        "inductive",
        "diagrammatic",
        "spatial",
        "memory",
    }

    ROLE_MAPPING = {
        "developer": ["technical", "problem_solving", "reasoning"],
        "manager": ["leadership", "decision_making", "communication"],
        "analyst": ["reasoning", "problem_solving", "technical"],
        "executive": ["leadership", "decision_making", "strategic"],
        "sales": ["communication", "persuasion", "negotiation"],
        "customer service": ["communication", "empathy", "teamwork"],
        "team lead": ["leadership", "communication", "teamwork"],
        "hr": ["communication", "empathy", "decision_making"],
    }

    SENIORITY_MAPPING = {
        "junior": [0, 3],  # 0-3 years
        "mid": [3, 7],  # 3-7 years
        "senior": [7, 15],  # 7-15 years
        "executive": [15, 100],  # 15+ years
    }

    @staticmethod
    def extract_keywords(text: str) -> Set[str]:
        """Extract and normalize keywords from text."""
        if not text:
            return set()

        text = text.lower()
        words = set()

        for word in text.split():
            # Clean punctuation
            word = word.strip(".,!?;:()[]{}\"'")
            if len(word) > 2:
                words.add(word)

        return words

    @staticmethod
    def detect_skills(assessment: Dict) -> Dict[str, List[str]]:
        """
        Detect skills measured by assessment.

        Returns:
            {
                'communication': [list of related keywords],
                'leadership': [...],
                'technical': [...],
                'personality': [...],
                'cognitive': [...]
            }
        """

        text = (
            (assessment.get("name") or "") + " "
            + (assessment.get("description") or "") + " "
            + " ".join(assessment.get("skills", []))
        ).lower()

        skills = {}

        # Communication
        comm_found = [kw for kw in MetadataEnricher.COMMUNICATION_KEYWORDS if kw in text]
        if comm_found:
            skills["communication"] = comm_found

        # Leadership
        lead_found = [kw for kw in MetadataEnricher.LEADERSHIP_KEYWORDS if kw in text]
        if lead_found:
            skills["leadership"] = lead_found

        # Technical
        tech_found = [kw for kw in MetadataEnricher.TECHNICAL_KEYWORDS if kw in text]
        if tech_found:
            skills["technical"] = tech_found

        # Personality
        pers_found = [kw for kw in MetadataEnricher.PERSONALITY_KEYWORDS if kw in text]
        if pers_found:
            skills["personality"] = pers_found

        # Cognitive
        cog_found = [kw for kw in MetadataEnricher.COGNITIVE_KEYWORDS if kw in text]
        if cog_found:
            skills["cognitive"] = cog_found

        return skills

    @staticmethod
    def infer_roles(assessment: Dict) -> List[str]:
        """
        Infer job roles this assessment is relevant for.

        Heuristics based on name, description, skills, and known patterns.
        """

        text = (
            (assessment.get("name") or "") + " "
            + (assessment.get("description") or "")
        ).lower()

        roles = set()

        # Check explicit role mentions
        for role, keywords in MetadataEnricher.ROLE_MAPPING.items():
            # Check if skills match
            if assessment.get("skills"):
                skills_str = " ".join(assessment["skills"]).lower()
                for keyword in keywords:
                    if keyword in skills_str or keyword in text:
                        roles.add(role)

        # Check assessment type hints
        if "personality" in text or "trait" in text:
            roles.update(["manager", "team lead", "executive"])

        if "technical" in text or "programming" in text:
            roles.update(["developer", "analyst"])

        if "reasoning" in text or "cognitive" in text:
            roles.update(["analyst", "developer", "executive"])

        return sorted(list(roles)) if roles else ["general"]

    @staticmethod
    def infer_seniority_levels(assessment: Dict) -> List[str]:
        """
        Infer appropriate seniority levels for this assessment.

        Some assessments are for specific levels (junior, mid, senior, exec).
        """

        text = (
            (assessment.get("name") or "") + " "
            + (assessment.get("description") or "")
        ).lower()

        levels = set()

        # Check for explicit seniority mentions
        seniority_keywords = {
            "junior": "junior",
            "mid": ["mid", "intermediate", "middle"],
            "senior": ["senior", "advanced"],
            "executive": ["executive", "senior management", "director"],
        }

        for level, keywords in seniority_keywords.items():
            if isinstance(keywords, str):
                keywords = [keywords]
            if any(kw in text for kw in keywords):
                levels.add(level)

        # If duration is short, likely for junior/mid
        duration = assessment.get("duration_minutes")
        if duration and duration < 20:
            levels.update(["junior", "mid"])

        # Default: suitable for all levels if no specificity found
        if not levels:
            levels = {"junior", "mid", "senior", "executive"}

        return sorted(list(levels))

    @staticmethod
    def infer_assessment_category(assessment: Dict) -> str:
        """
        Categorize assessment: personality, ability, knowledge, or hybrid.
        """

        test_type = assessment.get("test_type", "").upper()

        if test_type == "P":
            return "personality"
        elif test_type == "A":
            return "ability"
        elif test_type == "K":
            return "knowledge"
        else:
            text = (
                (assessment.get("name") or "") + " "
                + (assessment.get("description") or "")
            ).lower()

            if "personality" in text or "trait" in text:
                return "personality"
            elif "reasoning" in text or "cognitive" in text:
                return "ability"
            elif "knowledge" in text or "skill" in text:
                return "knowledge"
            else:
                return "ability"

    @staticmethod
    def calculate_relevance_scores(assessment: Dict) -> Dict[str, float]:
        """
        Calculate relevance scores for different use cases.

        Returns:
            {
                'communication_focus': 0.0-1.0,
                'leadership_focus': 0.0-1.0,
                'technical_focus': 0.0-1.0,
                'personality_focus': 0.0-1.0,
                'cognitive_focus': 0.0-1.0
            }
        """

        text = (
            (assessment.get("name") or "") + " "
            + (assessment.get("description") or "") + " "
            + " ".join(assessment.get("skills", []))
        ).lower()

        scores = {}

        # Communication score
        comm_matches = sum(
            1 for kw in MetadataEnricher.COMMUNICATION_KEYWORDS if kw in text
        )
        scores["communication_focus"] = min(comm_matches / 3, 1.0)

        # Leadership score
        lead_matches = sum(
            1 for kw in MetadataEnricher.LEADERSHIP_KEYWORDS if kw in text
        )
        scores["leadership_focus"] = min(lead_matches / 3, 1.0)

        # Technical score
        tech_matches = sum(
            1 for kw in MetadataEnricher.TECHNICAL_KEYWORDS if kw in text
        )
        scores["technical_focus"] = min(tech_matches / 3, 1.0)

        # Personality score
        pers_matches = sum(
            1 for kw in MetadataEnricher.PERSONALITY_KEYWORDS if kw in text
        )
        scores["personality_focus"] = min(pers_matches / 3, 1.0)

        # Cognitive score
        cog_matches = sum(
            1 for kw in MetadataEnricher.COGNITIVE_KEYWORDS if kw in text
        )
        scores["cognitive_focus"] = min(cog_matches / 3, 1.0)

        return scores

    @staticmethod
    def enrich_assessment(assessment: Dict) -> Dict:
        """
        Fully enrich a single assessment with inferred metadata.

        Adds:
        - domains
        - ideal_roles
        - seniority_fit
        - skill_tags
        - difficulty_level
        - recruiter_use_cases
        """

        enriched = assessment.copy()
        text = (assessment.get("name", "") + " " + assessment.get("description", "")).lower()

        # 1. Domains
        domains = []
        if "java" in text or "python" in text or "backend" in text: domains.append("backend")
        if "react" in text or "angular" in text or "frontend" in text or "css" in text: domains.append("frontend")
        if "data science" in text or "ml" in text or "machine learning" in text: domains.append("data_science")
        if "leadership" in text or "management" in text or "executive" in text: domains.append("leadership")
        if "sales" in text or "customer" in text: domains.append("sales")
        if "cognitive" in text or "reasoning" in text: domains.append("cognitive")
        if not domains: domains.append("general")
        enriched["domains"] = domains

        # 2. Ideal Roles
        roles = MetadataEnricher.infer_roles(assessment)
        if "general" in roles: roles = []
        # Add more specific roles based on name
        name = assessment.get("name", "").lower()
        if "java" in name: roles.extend(["Java Developer", "Backend Engineer"])
        if "python" in name: roles.extend(["Python Developer", "Data Engineer"])
        if "react" in name: roles.extend(["Frontend Developer", "React Engineer"])
        if "sales" in name: roles.extend(["Sales Representative", "Account Manager"])
        if "manager" in name: roles.extend(["Team Lead", "Engineering Manager"])
        enriched["ideal_roles"] = sorted(list(set(roles)))[:5]

        # 3. Seniority Fit
        enriched["seniority_fit"] = MetadataEnricher.infer_seniority_levels(assessment)

        # 4. Skill Tags
        skills = set(assessment.get("skills", []))
        # Add tags from name
        for word in name.split():
            if len(word) > 3 and word not in ["test", "short", "form", "solution"]:
                skills.add(word.capitalize())
        enriched["skill_tags"] = sorted(list(skills))[:8]

        # 5. Difficulty Level
        if "advanced" in text or "senior" in text or "executive" in text:
            enriched["difficulty_level"] = "advanced"
        elif "entry" in text or "junior" in text or "apprentice" in text:
            enriched["difficulty_level"] = "entry"
        else:
            enriched["difficulty_level"] = "intermediate"

        # 6. Recruiter Use Cases
        use_cases = []
        if "technical" in domains: use_cases.append("Technical skill verification")
        if "leadership" in domains: use_cases.append("Leadership readiness evaluation")
        if "sales" in domains: use_cases.append("Sales aptitude screening")
        if "personality" in text: use_cases.append("Culture fit assessment")
        if "cognitive" in domains: use_cases.append("General mental ability screening")
        if not use_cases: use_cases.append("General hiring assessment")
        enriched["recruiter_use_cases"] = use_cases[:3]

        # Legacy fields for backward compatibility
        enriched["inferred_skills"] = MetadataEnricher.detect_skills(assessment)
        enriched["inferred_roles"] = enriched["ideal_roles"]
        enriched["inferred_seniority_levels"] = enriched["seniority_fit"]
        enriched["category"] = MetadataEnricher.infer_assessment_category(assessment)
        enriched["relevance_scores"] = MetadataEnricher.calculate_relevance_scores(assessment)

        return enriched

    @staticmethod
    def enrich_catalog(assessments: List[Dict]) -> Dict:
        """
        Enrich entire catalog.

        Returns:
            {
                'enriched': [enriched assessments],
                'stats': {summary stats}
            }
        """

        logger.info(f"Enriching {len(assessments)} assessments")

        enriched = []
        for assessment in assessments:
            try:
                enriched_item = MetadataEnricher.enrich_assessment(assessment)
                enriched.append(enriched_item)
            except Exception as e:
                logger.warning(
                    f"Error enriching assessment {assessment.get('name')}: {e}"
                )
                enriched.append(assessment)

        # Calculate stats
        categories = {}
        skills_count = {}

        for item in enriched:
            cat = item.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

            for skill_type, skills in item.get("inferred_skills", {}).items():
                skills_count[skill_type] = skills_count.get(skill_type, 0) + len(
                    skills
                )

        return {
            "enriched": enriched,
            "stats": {
                "total_enriched": len(enriched),
                "categories": categories,
                "skills_found": skills_count,
            },
        }
