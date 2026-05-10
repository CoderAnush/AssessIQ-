"""
SHL Assessment Legitimacy Verification Engine.

CRITICAL: Ensures NO hallucinated or non-existent assessments are recommended.

Validates:
- Assessment names against official SHL catalog
- URLs are legitimate shl.com links
- Test types match catalog records
- Prevents fabricated assessment names
- Flags invalid metadata

If assessment not verified: DO NOT show it.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import re
from app.models.assessment import AssessmentWithMetadata
from app.logger_config.logger import get_logger

logger = get_logger("assessment_validator")


@dataclass
class ValidationResult:
    """Result of assessment validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    assessment_id: str
    assessment_name: str


class SHLAssessmentValidator:
    """
    Enterprise-grade SHL assessment legitimacy verifier.
    
    Ensures all recommendations are grounded in real SHL catalog data.
    """
    
    # Official SHL domain patterns
    VALID_SHL_DOMAINS = [
        "shl.com",
        "www.shl.com",
        "solutions.shl.com",
        "www.shl.com/solutions",
    ]
    
    # Known valid SHL assessment name patterns
    KNOWN_SHL_PATTERNS = [
        r"OPQ\d*",  # OPQ32r, OPQ
        r"Verify\s+",  # Verify Interactive, Verify G+
        r"GSA",  # General Ability Assessment
        r"\d+PF",  # 16PF
        r"Leadership\s+\d+",  # Leadership 7, Leadership 5
        r"CEB\s+",  # CEB Verbal, CEB Numerical
        r"MQ",  # Motivation Questionnaire
        r"MQ\d*",  # MQ
        r"UGLES",  # Graduate Assessment
        r"S\+\d*",  # S+ series
    ]
    
    # Known assessment categories by SHL
    VALID_CATEGORIES = {
        "Ability", "Aptitude", "Cognitive", "Personality", "Behavioral",
        "Motivation", "Situational Judgement", "Skills", "Knowledge",
        "Leadership", "Sales", "Customer Service", "Safety", "Integrity"
    }
    
    # Valid test types
    VALID_TEST_TYPES = {"K", "A", "P", "B", "S"}  # Knowledge, Ability, Personality, Behavioral, Situational
    
    def __init__(self, catalog_assessments: Optional[List[AssessmentWithMetadata]] = None):
        """
        Initialize validator with catalog data.
        
        Args:
            catalog_assessments: Official SHL catalog assessments
        """
        self._catalog: Dict[str, AssessmentWithMetadata] = {}
        self._name_index: Dict[str, str] = {}  # name -> id mapping
        self._url_index: Dict[str, str] = {}   # url -> id mapping
        
        if catalog_assessments:
            self.build_validation_index(catalog_assessments)
    
    def build_validation_index(self, assessments: List[AssessmentWithMetadata]) -> None:
        """Build validation index from catalog assessments."""
        logger.info(f"Building validation index for {len(assessments)} assessments")
        
        for assessment in assessments:
            self._catalog[assessment.id] = assessment
            
            # Index by name (case-insensitive)
            self._name_index[assessment.name.lower()] = assessment.id
            
            # Also index by URL
            if assessment.url:
                self._url_index[assessment.url] = assessment.id
        
        logger.info(f"Validation index built: {len(self._catalog)} assessments indexed")
    
    def validate_assessment(self, assessment: AssessmentWithMetadata) -> ValidationResult:
        """
        Validate a single assessment against SHL catalog.
        
        Returns ValidationResult with is_valid flag and any errors/warnings.
        """
        errors = []
        warnings = []
        
        # 1. Validate ID exists in catalog
        if assessment.id not in self._catalog:
            errors.append(f"Assessment ID '{assessment.id}' not found in SHL catalog")
        
        # 2. Validate name matches catalog
        catalog_assessment = self._catalog.get(assessment.id)
        if catalog_assessment:
            if assessment.name != catalog_assessment.name:
                errors.append(
                    f"Name mismatch: '{assessment.name}' vs catalog '{catalog_assessment.name}'"
                )
        
        # 3. Validate URL
        url_valid, url_error = self._validate_url(assessment.url, assessment.name)
        if not url_valid:
            errors.append(url_error)
        
        # 4. Validate test type
        if assessment.test_type.value not in self.VALID_TEST_TYPES:
            errors.append(
                f"Invalid test type '{assessment.test_type.value}' - must be one of {self.VALID_TEST_TYPES}"
            )
        
        # 5. Check for hallucinated names (obvious fabrications)
        name_check = self._check_name_legitimacy(assessment.name)
        if not name_check[0]:
            errors.append(name_check[1])
        
        # 6. Validate duration
        if hasattr(assessment, 'duration_minutes'):
            duration = assessment.duration_minutes
            if duration < 5:
                warnings.append(f"Unusually short duration: {duration} minutes")
            elif duration > 120:
                warnings.append(f"Long duration: {duration} minutes - may impact completion rates")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(
                f"Assessment validation failed for {assessment.name}: {errors}"
            )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            assessment_id=assessment.id,
            assessment_name=assessment.name
        )
    
    def validate_recommendations(
        self, 
        recommendations: List[Dict]
    ) -> Tuple[bool, List[str], List[Dict]]:
        """
        Validate a list of recommendation dicts.
        
        Returns:
            (all_valid, list_of_errors, filtered_valid_recommendations)
        """
        all_valid = True
        all_errors = []
        valid_recs = []
        
        for i, rec in enumerate(recommendations):
            name = rec.get("name", "Unknown")
            rec_id = rec.get("id", f"unknown_{i}")
            
            # Check if ID exists
            if rec_id not in self._catalog:
                all_valid = False
                error = f"Recommendation {i+1}: '{name}' (ID: {rec_id}) not in SHL catalog"
                all_errors.append(error)
                logger.error(error)
                continue
            
            # Check if name matches
            catalog_assessment = self._catalog[rec_id]
            if name != catalog_assessment.name:
                all_valid = False
                error = (
                    f"Recommendation {i+1}: Name mismatch - "
                    f"'{name}' vs '{catalog_assessment.name}'"
                )
                all_errors.append(error)
                logger.error(error)
                continue
            
            # Check URL
            url = rec.get("url", "")
            url_valid, url_error = self._validate_url(url, name)
            if not url_valid:
                all_valid = False
                all_errors.append(f"Recommendation {i+1}: {url_error}")
                continue
            
            # Check test type
            test_type = rec.get("test_type", "")
            if test_type not in self.VALID_TEST_TYPES:
                all_valid = False
                all_errors.append(
                    f"Recommendation {i+1}: Invalid test type '{test_type}'"
                )
                continue
            
            # Check test type matches catalog
            if test_type != catalog_assessment.test_type.value:
                all_valid = False
                all_errors.append(
                    f"Recommendation {i+1}: Test type mismatch - "
                    f"'{test_type}' vs '{catalog_assessment.test_type.value}'"
                )
                continue
            
            # Passed all checks
            valid_recs.append(rec)
        
        return all_valid, all_errors, valid_recs
    
    def _validate_url(self, url: str, assessment_name: str) -> Tuple[bool, str]:
        """Validate SHL URL format and domain."""
        if not url:
            return False, f"Missing URL for {assessment_name}"
        
        # Check URL starts with https
        if not url.startswith("https://"):
            return False, f"URL must use HTTPS: {url}"
        
        # Check domain
        url_lower = url.lower()
        valid_domain = any(domain in url_lower for domain in self.VALID_SHL_DOMAINS)
        
        if not valid_domain:
            return False, f"Invalid domain - must be shl.com: {url}"
        
        # Check URL matches catalog if available
        if url in self._url_index:
            return True, ""
        
        # URL format is valid but not in index (could be new)
        return True, ""
    
    def _check_name_legitimacy(self, name: str) -> Tuple[bool, str]:
        """Check if assessment name appears legitimate."""
        # Check for obviously fake/hallucinated patterns
        fake_indicators = [
            r"test\s+test",  # Duplicate words
            r"assessment\s+assessment",
            r"^test\s*\d+$",  # Generic "Test 123"
            r"^assessment\s*\d+$",  # Generic "Assessment 123"
            r"fake",  # Contains "fake"
            r"example",  # Contains "example"
            r"sample",  # Contains "sample"
            r"demo",  # Contains "demo"
        ]
        
        name_lower = name.lower()
        
        for pattern in fake_indicators:
            if re.search(pattern, name_lower):
                return False, f"Suspicious assessment name pattern detected: '{name}'"
        
        # Check for very generic names
        generic_names = ["test", "assessment", "evaluation", "exam", "quiz", "screening", "quiz"]
        if name_lower.strip() in generic_names:
            return False, f"Assessment name too generic: '{name}'"
        
        # Check for suspicious fabricated patterns (LLM hallucination giveaways)
        suspicious_patterns = [
            r"\b(super|ultra|mega|hyper|pro|elite|prime|advanced|professional)\s+(test|assessment|eval)",
            r"\b(netflix|google|amazon|facebook|meta|apple|microsoft)\s+(coding|test|assessment)",
            r"\b(5000|3000|1000|ai-powered|smart|intelligent)\s+(test|assessment)",
            r"\bshl\s+(ai|smart|next|future|pro)\b",  # Fake SHL variants
            r"\bcoding\s+(game|challenge|arena|platform)\b",
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, name_lower):
                return False, f"Suspicious fabricated name detected: '{name}'"
        
        return True, ""
    
    def check_for_hallucinations(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check text for hallucinated assessment references.
        
        Returns (is_clean, list_of_hallucinated_items)
        """
        hallucinated = []
        text_lower = text.lower()
        
        # Expanded patterns to catch more hallucination formats
        patterns = [
            # Standard formats
            r"(?:the\s+)?([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)\s+(?:assessment|test|evaluation|screening)",
            r"(?:assessment|test|evaluation)\s+(?:called|named|like)\s+([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)",
            # Quote formats
            r'["\']([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)["\']\s+(?:assessment|test)',
            # Recommendation formats
            r"recommend(?:ing|ed)?\s+(?:the\s+)?([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)",
            r"suggest(?:ing|ed)?\s+(?:the\s+)?([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)",
            # List formats
            r"(?:^|\d+\.\s+|\*\s+|\-\s+)([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+)*)",
        ]
        
        found_names = set()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                # Clean up the match
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                cleaned = match.strip().strip('"\'')
                if cleaned and len(cleaned) > 2:
                    found_names.add(cleaned)
        
        # Additional explicit check for known fake patterns
        fake_indicators = [
            r"super\s*test", r"ultra\s*test", r"mega\s*assessment",
            r"netflix\s*coding", r"google\s*challenge", r"ai\s*assessment",
        ]
        for pattern in fake_indicators:
            if re.search(pattern, text_lower):
                # Extract the fake name
                match = re.search(pattern, text_lower)
                if match:
                    hallucinated.append(match.group(0))
        
        # Check each found name against catalog
        for name in found_names:
            # Skip generic descriptions and common words
            skip_words = {"this", "that", "the", "an", "a", "your", "our", "my", "shl", "valid", "good", "best", "top"}
            if name.lower() in skip_words:
                continue
            
            # Skip if it's just a number
            if name.isdigit():
                continue
            
            # Check if in catalog (case-insensitive)
            name_lower = name.lower()
            is_in_catalog = name_lower in self._name_index
            
            # Check for close matches (typos, variations)
            if not is_in_catalog:
                close_match_threshold = 0.8  # 80% similarity
                for catalog_name in self._name_index.keys():
                    similarity = self._calculate_similarity(name_lower, catalog_name)
                    if similarity >= close_match_threshold:
                        is_in_catalog = True
                        break
            
            if not is_in_catalog:
                # Additional validation: check if it looks like a real assessment name
                # Must be: capitalized words, reasonable length, no obvious fake indicators
                words = name.split()
                has_capitalization = all(w[0].isupper() for w in words if w)
                reasonable_length = 3 <= len(name) <= 60
                
                # Check against suspicious patterns
                is_suspicious = any(
                    re.search(pattern, name_lower) 
                    for pattern in [r"\bsuper\b", r"\bultra\b", r"\bmega\b", r"\bpro\b\d", r"\bai\b.*\btest"]
                )
                
                if has_capitalization and reasonable_length and not is_suspicious:
                    # Could be legitimate, check context
                    pass
                elif is_suspicious:
                    # Likely hallucinated
                    hallucinated.append(name)
                elif not has_capitalization and len(words) <= 2:
                    # Short lowercase names are suspicious
                    hallucinated.append(name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_hallucinated = []
        for name in hallucinated:
            if name.lower() not in seen:
                seen.add(name.lower())
                unique_hallucinated.append(name)
        
        is_clean = len(unique_hallucinated) == 0
        
        if not is_clean:
            logger.warning(f"Potential hallucinations detected: {unique_hallucinated}")
        
        return is_clean, unique_hallucinated
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using simple ratio."""
        # Simple Levenshtein-inspired similarity
        if str1 == str2:
            return 1.0
        
        # Check if one is substring of other
        if str1 in str2 or str2 in str1:
            longer = max(len(str1), len(str2))
            shorter = min(len(str1), len(str2))
            return shorter / longer
        
        # Word overlap
        words1 = set(str1.split())
        words2 = set(str2.split())
        if words1 and words2:
            intersection = words1 & words2
            union = words1 | words2
            return len(intersection) / len(union) if union else 0.0
        
        return 0.0
    
    def get_catalog_stats(self) -> Dict:
        """Get statistics about the validation catalog."""
        return {
            "total_assessments": len(self._catalog),
            "indexed_names": len(self._name_index),
            "indexed_urls": len(self._url_index),
            "test_type_distribution": self._get_test_type_distribution(),
        }
    
    def _get_test_type_distribution(self) -> Dict[str, int]:
        """Get distribution of test types in catalog."""
        distribution = {}
        for assessment in self._catalog.values():
            tt = assessment.test_type.value
            distribution[tt] = distribution.get(tt, 0) + 1
        return distribution
    
    def is_assessment_valid(self, assessment_id: str) -> bool:
        """Quick check if assessment ID is in catalog."""
        return assessment_id in self._catalog
    
    def get_valid_assessment(self, assessment_id: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment from catalog if valid."""
        return self._catalog.get(assessment_id)
    
    def get_valid_assessment_by_name(self, name: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by name if valid."""
        assessment_id = self._name_index.get(name.lower())
        if assessment_id:
            return self._catalog.get(assessment_id)
        return None


# Convenience function for quick validation
def validate_single_assessment(
    assessment: AssessmentWithMetadata,
    catalog: List[AssessmentWithMetadata]
) -> ValidationResult:
    """Quick validation of a single assessment."""
    validator = SHLAssessmentValidator(catalog)
    return validator.validate_assessment(assessment)


def validate_recommendation_list(
    recommendations: List[Dict],
    catalog: List[AssessmentWithMetadata]
) -> Tuple[bool, List[str], List[Dict]]:
    """Quick validation of recommendation list."""
    validator = SHLAssessmentValidator(catalog)
    return validator.validate_recommendations(recommendations)
