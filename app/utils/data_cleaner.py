"""
Data cleaning and normalization pipeline for SHL assessment catalog.
Ensures data quality and consistency.
"""

import re
import json
from typing import Dict, List, Any, Optional
from html.parser import HTMLParser
import logging

logger = logging.getLogger(__name__)


class HTMLCleaner(HTMLParser):
    """Strip HTML tags from text."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed).strip()


class DataCleaner:
    """Cleans and normalizes assessment catalog data."""

    @staticmethod
    def clean_html(text: str) -> str:
        """Remove HTML tags and decode entities."""
        if not text:
            return ""

        # Decode common HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#039;", "'")

        # Strip HTML tags
        try:
            cleaner = HTMLCleaner()
            cleaner.feed(text)
            text = cleaner.get_data()
        except Exception as e:
            logger.warning(f"HTML cleaning failed: {e}")

        return text

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace."""
        if not text:
            return ""

        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    @staticmethod
    def normalize_text(text: str) -> str:
        """Full text normalization."""
        text = DataCleaner.clean_html(text)
        text = DataCleaner.normalize_whitespace(text)
        return text

    @staticmethod
    def normalize_duration(duration_str: str) -> Optional[int]:
        """
        Convert duration string to minutes.

        Examples:
            "45 minutes" -> 45
            "1 hour" -> 60
            "1.5 hours" -> 90
            "45" -> 45
        """
        if not duration_str:
            return None

        duration_str = str(duration_str).lower().strip()

        try:
            # Extract number
            match = re.search(r"(\d+\.?\d*)", duration_str)
            if not match:
                return None

            value = float(match.group(1))

            # Check for hour indicator
            if "hour" in duration_str:
                value = int(value * 60)
            else:
                value = int(value)

            # Sanity check (between 5 and 300 minutes)
            if 5 <= value <= 300:
                return value

            return None

        except Exception as e:
            logger.warning(f"Duration parsing failed for '{duration_str}': {e}")
            return None

    @staticmethod
    def detect_test_type(assessment_data: Dict) -> Optional[str]:
        """
        Detect assessment type: K (Knowledge), A (Ability), P (Personality).

        Heuristics:
        - Knowledge: keywords like "knowledge", "test", "certification"
        - Ability: keywords like "ability", "cognitive", "reasoning", "verbal", "numerical"
        - Personality: keywords like "personality", "traits", "behavior", "profile"
        """

        text = (
            (assessment_data.get("name") or "") + " "
            + (assessment_data.get("description") or "")
        ).lower()

        personality_keywords = [
            "personality",
            "trait",
            "behavior",
            "profile",
            "style",
            "preference",
            "otpq",
            "16pf",
            "opq",
        ]
        ability_keywords = [
            "ability",
            "cognitive",
            "reasoning",
            "verbal",
            "numerical",
            "logic",
            "deductive",
            "inductive",
            "diagrammatic",
            "gsa",
        ]
        knowledge_keywords = [
            "knowledge",
            "expertise",
            "skill test",
            "technical",
            "java",
            "python",
            "sql",
        ]

        personality_count = sum(1 for kw in personality_keywords if kw in text)
        ability_count = sum(1 for kw in ability_keywords if kw in text)
        knowledge_count = sum(1 for kw in knowledge_keywords if kw in text)

        if personality_count > ability_count and personality_count > knowledge_count:
            return "P"
        elif ability_count > knowledge_count:
            return "A"
        elif knowledge_count > 0:
            return "K"

        return None

    @staticmethod
    def validate_required_fields(assessment: Dict) -> tuple[bool, List[str]]:
        """
        Validate that assessment has all required fields.

        Required: name, url, description
        Optional: duration, skills, etc.
        """

        required = ["name", "url", "description"]
        missing = [field for field in required if not assessment.get(field)]

        return len(missing) == 0, missing

    @staticmethod
    def remove_duplicates(assessments: List[Dict]) -> tuple[List[Dict], int]:
        """
        Remove duplicate assessments based on URL.

        Returns:
            (unique_assessments, duplicate_count)
        """

        seen_urls = set()
        unique = []
        duplicates = 0

        for assessment in assessments:
            url = assessment.get("url", "").lower().strip()

            if url in seen_urls:
                duplicates += 1
                continue

            seen_urls.add(url)
            unique.append(assessment)

        return unique, duplicates

    @staticmethod
    def clean_assessment(assessment: Dict) -> Dict:
        """
        Fully clean a single assessment.

        Normalizes all text fields, detects missing fields, etc.
        """

        cleaned = {}

        # Clean name
        cleaned["name"] = DataCleaner.normalize_text(assessment.get("name", ""))

        # Clean URL (just normalize, don't validate here)
        cleaned["url"] = str(assessment.get("url", "")).strip().lower()

        # Clean description
        description = assessment.get("description", "")
        if not description:
            # Generate placeholder description from name and category
            category = assessment.get("category", "Professional")
            description = f"Standard SHL assessment for {assessment.get('name')}, focused on {category} evaluation."
        cleaned["description"] = DataCleaner.normalize_text(description)

        # Clean skills (if list)
        if isinstance(assessment.get("skills"), list):
            cleaned["skills"] = [
                DataCleaner.normalize_text(s) for s in assessment["skills"] if s
            ]
        elif assessment.get("skills"):
            cleaned["skills"] = [DataCleaner.normalize_text(assessment["skills"])]
        else:
            # Infer skills from name if missing
            name = assessment.get("name", "").lower()
            if "java" in name: cleaned["skills"] = ["Java", "Programming"]
            elif "python" in name: cleaned["skills"] = ["Python", "Programming"]
            elif "react" in name: cleaned["skills"] = ["React", "Frontend"]
            elif "angular" in name: cleaned["skills"] = ["Angular", "Frontend"]
            elif "data science" in name: cleaned["skills"] = ["Data Science", "Machine Learning"]
            elif "leadership" in name: cleaned["skills"] = ["Leadership", "Management"]
            elif "communication" in name: cleaned["skills"] = ["Communication", "Interpersonal"]
            else: cleaned["skills"] = []

        # Normalize duration
        cleaned["duration_minutes"] = DataCleaner.normalize_duration(
            assessment.get("duration_minutes") or assessment.get("duration")
        )

        # Detect test type
        detected_type = DataCleaner.detect_test_type(assessment)
        if not detected_type:
            # Try from category string
            cat_str = str(assessment.get("category", "")).lower()
            if "personality" in cat_str or "behavioral" in cat_str:
                detected_type = "P"
            elif "cognitive" in cat_str or "ability" in cat_str:
                detected_type = "A"
            elif "knowledge" in cat_str or "skill" in cat_str:
                detected_type = "K"
        
        if detected_type:
            cleaned["test_type"] = detected_type
        elif assessment.get("test_type"):
            cleaned["test_type"] = str(assessment.get("test_type")).upper()[0]
        else:
            cleaned["test_type"] = "K" # Default to Knowledge for general skills

        # Preserve other fields
        for key in [
            "id",
            "roles",
            "seniority_levels",
            "metadata",
            "job_relevance",
        ]:
            if key in assessment:
                cleaned[key] = assessment[key]

        return cleaned

    @staticmethod
    def clean_catalog(assessments: List[Dict]) -> Dict[str, Any]:
        """
        Full cleaning pipeline for catalog.

        Steps:
        1. Remove duplicates by URL
        2. Clean each assessment
        3. Validate required fields
        4. Return stats
        """

        logger.info(f"Starting catalog cleaning for {len(assessments)} assessments")

        # Remove duplicates
        unique, dup_count = DataCleaner.remove_duplicates(assessments)
        logger.info(f"Removed {dup_count} duplicates, {len(unique)} unique")

        # Clean each assessment
        cleaned = []
        invalid = []

        for assessment in unique:
            try:
                cleaned_item = DataCleaner.clean_assessment(assessment)

                # Validate
                is_valid, missing = DataCleaner.validate_required_fields(cleaned_item)
                if is_valid:
                    cleaned.append(cleaned_item)
                else:
                    invalid.append((assessment.get("name", "Unknown"), missing))

            except Exception as e:
                logger.warning(
                    f"Error cleaning assessment {assessment.get('name')}: {e}"
                )
                invalid.append((assessment.get("name", "Unknown"), [str(e)]))

        logger.info(f"Cleaned {len(cleaned)} assessments, {len(invalid)} invalid")

        return {
            "cleaned": cleaned,
            "invalid": invalid,
            "stats": {
                "input_count": len(assessments),
                "duplicates_removed": dup_count,
                "unique_count": len(unique),
                "valid_count": len(cleaned),
                "invalid_count": len(invalid),
                "success_rate": (
                    len(cleaned) / len(unique) * 100 if unique else 0
                ),
            },
        }
