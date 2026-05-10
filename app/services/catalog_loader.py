"""
Catalog loader service.
Loads SHL assessment catalog from JSON file.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from app.models.assessment import AssessmentWithMetadata
from app.logging.logger import get_logger

logger = get_logger("catalog_loader")


class CatalogLoader:
    """Loads and manages SHL assessment catalog."""

    def __init__(self, catalog_path: str):
        """
        Initialize catalog loader.

        Args:
            catalog_path: Path to catalog.json file
        """
        self.catalog_path = Path(catalog_path)
        self.assessments: List[AssessmentWithMetadata] = []
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Load catalog from JSON file."""
        if not self.catalog_path.exists():
            logger.warning(f"Catalog not found at {self.catalog_path}")
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse assessments with failsafe repair
            import re
            for i, item in enumerate(data.get("assessments", [])):
                try:
                    # Failsafe repairs
                    if not item.get("id"):
                        name = item.get("name") or f"unnamed-{i}"
                        id_name = name.lower()
                        id_name = id_name.replace("c#", "c-sharp").replace("c++", "c-plus-plus")
                        item["id"] = re.sub(r'[^a-z0-9]+', '-', id_name).strip('-')
                    
                    if item.get("duration_minutes") is None:
                        item["duration_minutes"] = 30
                    
                    if not item.get("test_type"):
                        item["test_type"] = "K"

                    assessment = AssessmentWithMetadata(**item)
                    self.assessments.append(assessment)
                except Exception as e:
                    logger.error(f"Failed to parse assessment {item.get('id') or i}: {e}")

            logger.info(f"Loaded {len(self.assessments)} assessments from catalog")

        except Exception as e:
            logger.error(f"Failed to load catalog: {e}")
            raise

    def get_all(self) -> List[AssessmentWithMetadata]:
        """Get all assessments."""
        return self.assessments

    def get_by_id(self, assessment_id: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by ID."""
        for assessment in self.assessments:
            if assessment.id == assessment_id:
                return assessment
        return None

    def get_by_name(self, name: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by name."""
        for assessment in self.assessments:
            if assessment.name.lower() == name.lower():
                return assessment
        return None

    def get_by_skill(self, skill: str) -> List[AssessmentWithMetadata]:
        """Get all assessments measuring a skill."""
        return [
            a for a in self.assessments
            if skill.lower() in [s.lower() for s in a.skills]
        ]

    def get_by_role(self, role: str) -> List[AssessmentWithMetadata]:
        """Get all assessments for a role."""
        return [
            a for a in self.assessments
            if role.lower() in [r.lower() for r in a.recommended_roles]
        ]

    def get_by_seniority(self, seniority: str) -> List[AssessmentWithMetadata]:
        """Get all assessments for seniority level."""
        return [
            a for a in self.assessments
            if seniority.lower() in [s.lower() for s in a.seniority_levels]
        ]

    def get_by_type(self, test_type: str) -> List[AssessmentWithMetadata]:
        """Get all assessments of a specific type."""
        return [
            a for a in self.assessments
            if a.test_type.value == test_type
        ]

    def validate(self) -> bool:
        """Validate catalog integrity."""
        if not self.assessments:
            logger.error("Catalog is empty")
            return False

        errors = []

        for assessment in self.assessments:
            # Check required fields
            if not assessment.id or not assessment.name or not assessment.url:
                errors.append(f"Assessment {assessment.name} missing required fields")

            # Check URL format
            if not assessment.url.startswith("https://www.shl.com"):
                errors.append(f"Assessment {assessment.name} has invalid URL")

        if errors:
            logger.error(f"Catalog validation failed: {errors}")
            return False

        logger.info("Catalog validation passed")
        return True

    def get_stats(self) -> Dict:
        """Get catalog statistics."""
        return {
            "total_assessments": len(self.assessments),
            "by_type": {
                "K": len(self.get_by_type("K")),
                "A": len(self.get_by_type("A")),
                "P": len(self.get_by_type("P")),
            },
            "avg_duration": sum(a.duration_minutes for a in self.assessments) / len(self.assessments) if self.assessments else 0,
            "total_skills": len(set(s for a in self.assessments for s in a.skills)),
            "total_roles": len(set(r for a in self.assessments for r in a.recommended_roles))
        }
