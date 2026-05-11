"""
Metadata Enrichment Pipeline - Expands SHL assessment catalogs with semantic metadata.
Generates role aliases, domain aliases, inferred skills, and engineering categories.
"""

import json
from typing import Dict, List, Set, Optional, Any
from app.logger_config.logger import get_logger

logger = get_logger("metadata_enricher")


class AssessmentEnricher:
    """Enriches assessments with semantic metadata for better matching."""

    # Domain-specific enrichment mappings
    DOMAIN_EXPANSIONS = {
        "Python": {
            "expanded_tags": ["python", "backend", "django", "flask", "fastapi", "api", "microservices", "web development", "server-side"],
            "role_aliases": ["python backend engineer", "python developer", "backend engineer", "api developer"],
            "engineering_category": "python_backend",
        },
        "Java": {
            "expanded_tags": ["java", "backend", "spring", "j2ee", "hibernate", "enterprise", "microservices", "api"],
            "role_aliases": ["java backend engineer", "java developer", "enterprise developer", "spring developer"],
            "engineering_category": "java_backend",
        },
        "React": {
            "expanded_tags": ["react", "frontend", "javascript", "typescript", "ui", "client-side", "web development", "nextjs", "vue"],
            "role_aliases": ["react developer", "frontend engineer", "javascript developer", "ui engineer", "frontend developer"],
            "engineering_category": "frontend",
        },
        "Testing": {
            "expanded_tags": ["testing", "qa", "automation", "quality assurance", "sdet", "selenium", "test engineer", "validation", "agile testing"],
            "role_aliases": ["qa engineer", "test automation engineer", "quality assurance engineer", "sdet", "qa automation engineer"],
            "engineering_category": "qa_automation",
        },
        "Data Science": {
            "expanded_tags": ["data science", "machine learning", "python", "statistics", "pandas", "numpy", "scikit-learn", "data analysis"],
            "role_aliases": ["data scientist", "ml engineer", "data analyst", "quantitative researcher"],
            "engineering_category": "data_science",
        },
        "ML Engineering": {
            "expanded_tags": ["machine learning", "mlops", "deep learning", "pytorch", "tensorflow", "neural networks", "model deployment"],
            "role_aliases": ["ml engineer", "machine learning engineer", "ai engineer", "deep learning engineer"],
            "engineering_category": "ml_engineering",
        },
        "AWS": {
            "expanded_tags": ["aws", "cloud", "backend", "infrastructure", "devops", "distributed systems", "api", "microservices"],
            "role_aliases": ["aws engineer", "cloud engineer", "backend engineer", "devops engineer"],
            "engineering_category": "devops",
        },
        "DevOps": {
            "expanded_tags": ["devops", "kubernetes", "docker", "infrastructure", "ci/cd", "cloud", "deployment", "terraform"],
            "role_aliases": ["devops engineer", "sre", "infrastructure engineer", "cloud engineer", "site reliability engineer"],
            "engineering_category": "devops",
        },
        "Cybersecurity": {
            "expanded_tags": ["cybersecurity", "security", "infosec", "network security", "pentesting", "vulnerability assessment"],
            "role_aliases": ["security engineer", "cybersecurity analyst", "security consultant", "infosec engineer"],
            "engineering_category": "cybersecurity",
        },
        "Leadership": {
            "expanded_tags": ["leadership", "management", "executive", "team management", "strategy", "organizational", "operations"],
            "role_aliases": ["manager", "team lead", "director", "executive", "engineering manager"],
            "engineering_category": "management",
        },
        "Sales": {
            "expanded_tags": ["sales", "commercial", "revenue", "account management", "business development", "customer facing"],
            "role_aliases": ["sales representative", "account executive", "business development", "sales manager"],
            "engineering_category": "sales",
        },
    }

    # Skill inference rules
    SKILL_INFERENCE_RULES = {
        "python": ["backend", "api", "microservices", "web development"],
        "java": ["backend", "enterprise", "microservices", "spring framework"],
        "react": ["frontend", "ui", "javascript", "typescript"],
        "testing": ["quality assurance", "automation", "validation", "debugging"],
        "aws": ["cloud", "infrastructure", "distributed systems", "microservices"],
        "kubernetes": ["container orchestration", "infrastructure", "devops"],
        "sql": ["database", "data analysis", "backend"],
        "leadership": ["team management", "strategic thinking", "communication"],
    }

    # Use case mapping
    USE_CASE_MAPPING = {
        "backend": [
            "screening backend engineers",
            "evaluating api design skills",
            "assessing system design knowledge",
            "filtering senior backend candidates",
        ],
        "frontend": [
            "screening frontend engineers",
            "evaluating ui/ux knowledge",
            "assessing javascript expertise",
            "filtering react developers",
        ],
        "qa": [
            "screening test automation engineers",
            "evaluating qa mindset",
            "assessing testing expertise",
            "filtering sdet candidates",
        ],
        "data": [
            "screening data analysts",
            "evaluating sql expertise",
            "assessing analytics knowledge",
            "filtering data scientists",
        ],
        "leadership": [
            "evaluating leadership potential",
            "screening team leads",
            "assessing management readiness",
            "cultural fit assessment",
        ],
        "sales": [
            "screening account executives",
            "evaluating persuasion skills",
            "assessing communication",
            "filtering sales representatives",
        ],
    }

    def __init__(self):
        """Initialize enricher with domain mappings."""
        self.domain_keywords = self._build_domain_keywords()

    def _build_domain_keywords(self) -> Dict[str, List[str]]:
        """Build searchable keyword index for domains."""
        keywords = {}
        for domain, data in self.DOMAIN_EXPANSIONS.items():
            keywords[domain.lower()] = data["expanded_tags"]
        return keywords

    def enrich_assessment(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single assessment with semantic metadata."""
        # Preserve original fields
        enriched = assessment.copy()

        # Infer domain from existing metadata
        inferred_domain = self._infer_domain(assessment)

        # Generate expanded tags
        enriched["expanded_tags"] = self._generate_expanded_tags(assessment, inferred_domain)

        # Generate role aliases
        enriched["role_aliases"] = self._generate_role_aliases(assessment, inferred_domain)

        # Generate domain aliases
        enriched["domain_aliases"] = self._generate_domain_aliases(assessment, inferred_domain)

        # Infer skills
        enriched["inferred_skills"] = self._infer_skills(assessment, inferred_domain)

        # Generate use cases
        enriched["inferred_use_cases"] = self._generate_use_cases(assessment, inferred_domain)

        # Assign engineering category
        enriched["engineering_category"] = self._assign_engineering_category(assessment, inferred_domain)

        return enriched

    def _infer_domain(self, assessment: Dict) -> str:
        """Infer primary domain from assessment metadata."""
        name_lower = assessment.get("name", "").lower()
        desc_lower = assessment.get("description", "").lower()
        combined = f"{name_lower} {desc_lower}"

        # Check skill tags first
        skill_tags = [s.lower() for s in assessment.get("skill_tags", [])]

        # Score each domain
        domain_scores = {}
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for kw in keywords if kw in combined or kw in skill_tags)
            if score > 0:
                domain_scores[domain] = score

        # Return highest scoring domain
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)

        # Fallback to skill tags
        if skill_tags:
            return skill_tags[0]

        return "general"

    def _generate_expanded_tags(self, assessment: Dict, domain: str) -> List[str]:
        """Generate expanded tag list for assessment."""
        existing_tags = set(assessment.get("skill_tags", []))
        expanded = list(existing_tags)

        # Add domain-specific expansions
        if domain in self.DOMAIN_EXPANSIONS:
            domain_tags = self.DOMAIN_EXPANSIONS[domain]["expanded_tags"]
            expanded.extend([t for t in domain_tags if t.lower() not in {e.lower() for e in expanded}])

        # Add inferred tags based on ideal roles
        for role in assessment.get("ideal_roles", []):
            role_lower = role.lower()
            if "manager" in role_lower or "lead" in role_lower:
                expanded.extend(["leadership", "team management"])
            if "backend" in role_lower:
                expanded.extend(["backend", "api", "server-side"])
            if "frontend" in role_lower:
                expanded.extend(["frontend", "ui", "client-side"])
            if "engineer" in role_lower:
                expanded.extend(["engineering", "technical"])

        # Remove duplicates and normalize
        return list(set(t.lower() for t in expanded if t))

    def _generate_role_aliases(self, assessment: Dict, domain: str) -> List[str]:
        """Generate role aliases for assessment."""
        aliases = set()

        # Add ideal roles
        for role in assessment.get("ideal_roles", []):
            aliases.add(role.lower())

        # Add domain-specific aliases
        if domain in self.DOMAIN_EXPANSIONS:
            aliases.update(self.DOMAIN_EXPANSIONS[domain]["role_aliases"])

        # Add derived aliases from assessment name
        name_lower = assessment.get("name", "").lower()
        if "python" in name_lower:
            aliases.add("python backend engineer")
            aliases.add("python developer")
        if "java" in name_lower:
            aliases.add("java backend engineer")
            aliases.add("java developer")
        if "react" in name_lower:
            aliases.add("react developer")
            aliases.add("frontend engineer")
        if "testing" in name_lower or "automation" in name_lower:
            aliases.add("qa engineer")
            aliases.add("test automation engineer")

        return list(aliases)

    def _generate_domain_aliases(self, assessment: Dict, domain: str) -> List[str]:
        """Generate domain aliases (alternative domain names)."""
        aliases = {domain}

        # Add semantic domain aliases
        domain_mapping = {
            "python": ["python backend", "backend", "api development"],
            "java": ["java backend", "backend", "enterprise"],
            "react": ["frontend", "javascript", "ui development"],
            "testing": ["qa", "quality assurance", "automation", "agile testing"],
            "aws": ["cloud", "devops", "infrastructure"],
            "devops": ["cloud", "sre", "infrastructure"],
            "data science": ["machine learning", "ai", "data analytics"],
            "ml engineering": ["machine learning", "ai", "deep learning"],
            "cybersecurity": ["security", "infosec", "network security"],
            "leadership": ["management", "team lead", "engineering manager"],
        }

        if domain in domain_mapping:
            aliases.update(domain_mapping[domain])

        return list(aliases)

    def _infer_skills(self, assessment: Dict, domain: str) -> List[str]:
        """Infer skills from assessment metadata."""
        skills = set()

        # Add skills from assessment
        skills.update(assessment.get("skills", []))

        # Add inferred from domain
        if domain in self.SKILL_INFERENCE_RULES:
            skills.update(self.SKILL_INFERENCE_RULES[domain])

        # Add from skill tags
        skills.update(assessment.get("skill_tags", []))

        # Add from ideal roles
        for role in assessment.get("ideal_roles", []):
            if "engineer" in role.lower():
                skills.add("engineering")
            if "manager" in role.lower():
                skills.add("management")
            if "developer" in role.lower():
                skills.add("development")

        return list(skills)

    def _generate_use_cases(self, assessment: Dict, domain: str) -> List[str]:
        """Generate recruiter use cases for assessment."""
        use_cases = list(assessment.get("recruiter_use_cases", []))

        # Add domain-specific use cases
        for domain_key, cases in self.USE_CASE_MAPPING.items():
            if domain_key.lower() in domain.lower() or domain_key.lower() in assessment.get("name", "").lower():
                use_cases.extend(cases)

        # Remove duplicates
        return list(set(use_cases))

    def _assign_engineering_category(self, assessment: Dict, domain: str) -> str:
        """Assign engineering category to assessment."""
        if domain in self.DOMAIN_EXPANSIONS:
            return self.DOMAIN_EXPANSIONS[domain].get("engineering_category", "general")

        # Infer from ideal roles
        for role in assessment.get("ideal_roles", []):
            role_lower = role.lower()
            if "manager" in role_lower:
                return "management"
            if "frontend" in role_lower:
                return "frontend"
            if "backend" in role_lower:
                return "backend"
            if "data" in role_lower or "scientist" in role_lower:
                return "data_science"
            if "ml" in role_lower or "machine learning" in role_lower:
                return "ml_engineering"
            if "security" in role_lower:
                return "cybersecurity"

        return "general"

    def enrich_catalog(self, catalog: Dict) -> Dict:
        """Enrich entire catalog."""
        enriched_assessments = []

        for assessment in catalog.get("assessments", []):
            try:
                enriched = self.enrich_assessment(assessment)
                enriched_assessments.append(enriched)
            except Exception as e:
                logger.error(f"Error enriching {assessment.get('name')}: {e}")
                # Fall back to original
                enriched_assessments.append(assessment)

        return {
            "assessments": enriched_assessments,
            "metadata": {
                "enriched": True,
                "version": "1.0",
            }
        }


def enrich_catalog_file(input_path: str, output_path: str) -> None:
    """Enrich catalog from JSON file and save to new file."""
    logger.info(f"Loading catalog from {input_path}")

    with open(input_path, "r") as f:
        catalog = json.load(f)

    logger.info(f"Enriching {len(catalog.get('assessments', []))} assessments")

    enricher = AssessmentEnricher()
    enriched = enricher.enrich_catalog(catalog)

    logger.info(f"Saving enriched catalog to {output_path}")

    with open(output_path, "w") as f:
        json.dump(enriched, f, indent=2)

    logger.info("Enrichment complete")


if __name__ == "__main__":
    import sys

    input_file = sys.argv[1] if len(sys.argv) > 1 else "data/processed/catalog_processed.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data/processed/catalog_enriched.json"

    enrich_catalog_file(input_file, output_file)
