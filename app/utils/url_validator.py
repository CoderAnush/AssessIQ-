"""
URL validation and normalization for SHL catalog.
Ensures all URLs are legitimate SHL assessment links.
Prevents hallucinated or malicious URLs.
"""

import re
from typing import Tuple
from urllib.parse import urlparse, urljoin
import logging

logger = logging.getLogger(__name__)


class URLValidator:
    """Validates and normalizes SHL assessment URLs."""

    VALID_SHL_DOMAINS = [
        "shl.com",
        "www.shl.com",
        "talentlens.com",
        "www.talentlens.com",
    ]

    SHL_ASSESSMENT_PATTERNS = [
        r"https?://(?:www\.)?shl\.com/[a-z0-9/_-]+",
        r"https?://(?:www\.)?talentlens\.com/[a-z0-9/_-]+",
    ]

    @classmethod
    def is_valid_shl_url(cls, url: str) -> Tuple[bool, str]:
        """
        Validate that URL is a legitimate SHL assessment link.

        Args:
            url: URL to validate

        Returns:
            (is_valid, message)
        """

        if not url:
            return False, "URL is empty"

        url = url.strip()

        # Must start with https
        if not url.startswith("https://"):
            return False, "URL must use HTTPS"

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"Invalid URL format: {e}"

        # Check domain
        domain = parsed.netloc.lower()
        if not any(domain.endswith(valid) or domain == valid for valid in cls.VALID_SHL_DOMAINS):
            return False, f"Domain must be SHL (got {domain})"

        # Check path (must have assessment identifier)
        path = parsed.path.lower()
        if not path or path == "/":
            return False, "URL path is missing assessment identifier"

        # Check for suspicious patterns
        if any(x in path for x in ["admin", "login", "api", "internal", ".php", ".asp"]):
            return False, "URL contains suspicious path"

        # Check against known assessment patterns
        full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if not any(re.match(pattern, full_url, re.IGNORECASE) for pattern in cls.SHL_ASSESSMENT_PATTERNS):
            logger.warning(f"URL doesn't match expected assessment pattern: {full_url}")

        return True, "Valid SHL URL"

    @classmethod
    def normalize_url(cls, url: str) -> str:
        """
        Normalize URL for consistent storage and retrieval.

        Args:
            url: Raw URL

        Returns:
            Normalized URL
        """

        if not url:
            return ""

        url = url.strip()

        # Remove trailing slashes (except domain)
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        # Remove query params and fragments
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"

        # Convert domain to lowercase
        if "://" in normalized:
            scheme, rest = normalized.split("://", 1)
            domain, path = (rest.split("/", 1) + [""])[:2]
            normalized = f"{scheme}://{domain.lower()}/{path}" if path else f"{scheme}://{domain.lower()}"

        return normalized

    @classmethod
    def extract_assessment_id(cls, url: str) -> str:
        """
        Extract assessment identifier from URL.

        Examples:
            https://www.shl.com/en-gb/solutions/products/opq32r/ -> opq32r
            https://www.shl.com/solutions/products/oasys/ -> oasys

        Args:
            url: SHL assessment URL

        Returns:
            Assessment ID (lowercase)
        """

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Get last path segment
        segments = [s for s in path.split("/") if s]
        if segments:
            assessment_id = segments[-1].lower()
            # Remove common suffixes
            assessment_id = re.sub(r"[-_]$", "", assessment_id)
            return assessment_id

        return ""

    @classmethod
    def validate_and_normalize_batch(cls, urls: list) -> dict:
        """
        Validate and normalize multiple URLs.

        Args:
            urls: List of URLs

        Returns:
            {
                'valid': [normalized URLs],
                'invalid': [(url, reason)],
                'duplicates': [assessment_ids]
            }
        """

        valid = []
        invalid = []
        seen_ids = set()
        duplicates = []

        for url in urls:
            is_valid, reason = cls.is_valid_shl_url(url)

            if not is_valid:
                invalid.append((url, reason))
                continue

            normalized = cls.normalize_url(url)
            assessment_id = cls.extract_assessment_id(normalized)

            if assessment_id in seen_ids:
                duplicates.append(assessment_id)
                continue

            seen_ids.add(assessment_id)
            valid.append(normalized)

        return {
            "valid": valid,
            "invalid": invalid,
            "duplicates": duplicates,
            "stats": {
                "total": len(urls),
                "valid_count": len(valid),
                "invalid_count": len(invalid),
                "duplicate_count": len(duplicates),
            },
        }
