"""
SHL Catalog Scraper - Production-Grade Web Scraper Architecture

IMPORTANT LEGAL NOTICE:
This scraper is provided as a technical reference implementation.
Before using this scraper on any live website:
1. Review SHL's Terms of Service and robots.txt
2. Obtain explicit permission if required
3. Respect rate limiting and robots.txt directives
4. Use responsibly and ethically

This implementation includes:
- Responsible rate limiting
- Proper error handling and retries
- User-agent identification
- Timeout handling
- Graceful degradation
- Comprehensive logging

For this project, you can use the sample catalog in data/raw/catalog.json
or implement this scraper with proper authorization.
"""

import json
import logging
import time
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
import random

logger = logging.getLogger(__name__)


class SHLScraper:
    """
    Production-grade SHL catalog scraper.

    IMPORTANT: Use this only with proper authorization.
    See documentation at: https://www.shl.com/en-gb/about/contact
    """

    # Conservative rate limiting - respect the server
    MIN_DELAY_BETWEEN_REQUESTS = 2.0  # seconds
    MAX_DELAY_BETWEEN_REQUESTS = 5.0  # seconds
    TIMEOUT = 10  # seconds per request
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0  # exponential backoff multiplier

    # SHL URLs
    BASE_URL = "https://www.shl.com"
    PRODUCTS_PATH = "/en-gb/solutions/products/"

    def __init__(self, use_cache: bool = True, cache_dir: str = "data/cache"):
        """
        Initialize scraper.

        Args:
            use_cache: Whether to cache responses
            cache_dir: Directory for cache files
        """
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.session = None
        self.assessments = []

        self._log_legal_notice()

    def _log_legal_notice(self) -> None:
        """Log legal considerations."""
        logger.info(
            "\n"
            "=" * 80 + "\n"
            "SHL SCRAPER LEGAL NOTICE\n"
            "=" * 80 + "\n"
            "This scraper is provided for educational and authorized use only.\n"
            "Ensure you have:\n"
            "1. Reviewed SHL's Terms of Service\n"
            "2. Obtained necessary permissions\n"
            "3. Respect robots.txt and rate limiting\n"
            "4. Use this responsibly\n"
            "=" * 80 + "\n"
        )

    def _get_session(self):
        """Get or create requests session with proper headers."""
        if self.session is None:
            try:
                import requests

                self.session = requests.Session()

                # Identify ourselves responsibly
                user_agent = (
                    "AssessIQ-Scraper/1.0 (+https://github.com/yourusername/assessiq) "
                    "Python-Requests"
                )
                self.session.headers.update({"User-Agent": user_agent})

                logger.info("Created HTTP session with proper User-Agent")

            except ImportError:
                logger.error(
                    "requests library not installed. "
                    "Install with: pip install requests"
                )
                raise

        return self.session

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        from urllib.parse import quote

        filename = quote(url, safe="")[:100] + ".json"
        return self.cache_dir / filename

    def _load_from_cache(self, url: str) -> Optional[Dict]:
        """Load cached response if available."""
        if not self.use_cache:
            return None

        cache_path = self._get_cache_path(url)

        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                logger.debug(f"Loaded from cache: {url}")
                return data
            except Exception as e:
                logger.warning(f"Error reading cache: {e}")

        return None

    def _save_to_cache(self, url: str, data: Dict) -> None:
        """Save response to cache."""
        if not self.use_cache:
            return

        cache_path = self._get_cache_path(url)

        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
            logger.debug(f"Cached: {url}")
        except Exception as e:
            logger.warning(f"Error writing cache: {e}")

    def _fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch URL with retries and rate limiting.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None on failure
        """

        session = self._get_session()

        # Respect rate limiting
        delay = random.uniform(
            self.MIN_DELAY_BETWEEN_REQUESTS, self.MAX_DELAY_BETWEEN_REQUESTS
        )
        logger.debug(f"Rate limiting: waiting {delay:.1f}s")
        time.sleep(delay)

        # Retry loop
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"Fetching: {url} (attempt {attempt + 1})")

                response = session.get(url, timeout=self.TIMEOUT)
                response.raise_for_status()

                logger.info(f"✓ Fetched: {url}")
                return response.text

            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")

                if attempt < self.MAX_RETRIES - 1:
                    # Exponential backoff
                    backoff = self.RETRY_BACKOFF ** attempt
                    logger.info(f"Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed to fetch {url} after {self.MAX_RETRIES} retries")
                    return None

        return None

    def _parse_assessment(self, name: str, url: str, **kwargs) -> Dict:
        """
        Parse assessment data into standard format.

        Args:
            name: Assessment name
            url: Assessment URL
            **kwargs: Additional fields

        Returns:
            Standardized assessment dict
        """

        assessment = {
            "id": name.lower().replace(" ", "_"),
            "name": name.strip(),
            "url": urljoin(self.BASE_URL, url) if not url.startswith("http") else url,
            "description": kwargs.get("description", ""),
            "skills": kwargs.get("skills", []),
            "duration": kwargs.get("duration"),
            "test_type": kwargs.get("test_type"),
            "job_relevance": kwargs.get("job_relevance", []),
            "metadata": {
                "scraped_at": datetime.now().isoformat(),
                "source": "shl.com",
            },
        }

        return assessment

    def scrape_products_page(self) -> List[Dict]:
        """
        Scrape SHL products/assessments page.

        This is a template - actual implementation depends on page structure.
        """

        logger.info("Scraping SHL products page...")

        url = urljoin(self.BASE_URL, self.PRODUCTS_PATH)

        # Check cache first
        cached = self._load_from_cache(url)
        if cached:
            logger.info(f"Using cached data for {url}")
            return cached.get("assessments", [])

        # Fetch page
        html = self._fetch_url(url)
        if not html:
            logger.error("Failed to fetch products page")
            return []

        assessments = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Find assessment cards (selector varies by page structure)
            # This is a template - adjust selectors for actual HTML
            cards = soup.find_all("div", class_=["product-card", "assessment"])

            logger.info(f"Found {len(cards)} assessment cards")

            for card in cards:
                try:
                    # Extract name
                    name_elem = card.find(["h2", "h3", "h4"])
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)

                    # Extract URL
                    link_elem = card.find("a", href=True)
                    if not link_elem:
                        continue

                    url = link_elem["href"]

                    # Extract description
                    desc_elem = card.find(["p", "div"], class_="description")
                    description = (
                        desc_elem.get_text(strip=True) if desc_elem else ""
                    )

                    # Extract metadata (skills, duration, etc.)
                    skills = []
                    skill_elems = card.find_all(["span", "tag"], class_="skill")
                    if skill_elems:
                        skills = [
                            s.get_text(strip=True) for s in skill_elems
                        ]

                    # Create assessment
                    assessment = self._parse_assessment(
                        name,
                        url,
                        description=description,
                        skills=skills,
                    )

                    assessments.append(assessment)
                    logger.debug(f"Parsed: {name}")

                except Exception as e:
                    logger.warning(f"Error parsing card: {e}")
                    continue

            # Cache results
            self._save_to_cache(
                url, {"assessments": assessments, "scraped_at": datetime.now().isoformat()}
            )

            logger.info(f"Scraped {len(assessments)} assessments")
            return assessments

        except ImportError:
            logger.error(
                "BeautifulSoup not installed. "
                "Install with: pip install beautifulsoup4"
            )
            raise

        except Exception as e:
            logger.error(f"Error scraping page: {e}", exc_info=True)
            return []

    def scrape_assessment_details(self, assessment_url: str) -> Dict:
        """
        Scrape detailed information for a single assessment.

        Args:
            assessment_url: Full URL to assessment page

        Returns:
            Enriched assessment dict
        """

        logger.info(f"Scraping details: {assessment_url}")

        # Check cache
        cached = self._load_from_cache(assessment_url)
        if cached:
            logger.debug("Using cached details")
            return cached

        html = self._fetch_url(assessment_url)
        if not html:
            logger.warning(f"Failed to fetch: {assessment_url}")
            return {}

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            details = {
                "duration_minutes": None,
                "test_type": None,
                "full_description": "",
                "benefits": [],
                "use_cases": [],
            }

            # Extract duration (template - adjust selectors)
            duration_elem = soup.find(["span", "div"], class_="duration")
            if duration_elem:
                duration_text = duration_elem.get_text(strip=True)
                # Parse "45 minutes" -> 45
                import re

                match = re.search(r"(\d+)", duration_text)
                if match:
                    details["duration_minutes"] = int(match.group(1))

            # Cache
            self._save_to_cache(assessment_url, details)
            logger.debug(f"Cached details: {assessment_url}")

            return details

        except ImportError:
            logger.error("BeautifulSoup not installed")
            return {}

        except Exception as e:
            logger.warning(f"Error parsing details: {e}")
            return {}

    def scrape_full_catalog(self) -> List[Dict]:
        """
        Scrape complete SHL assessment catalog.

        Steps:
        1. Scrape products page to get assessment list
        2. Scrape individual assessment pages for details
        3. Validate and deduplicate
        """

        logger.info("=" * 80)
        logger.info("STARTING FULL CATALOG SCRAPE")
        logger.info("=" * 80)

        try:
            # Step 1: Get assessment list
            assessments = self.scrape_products_page()

            if not assessments:
                logger.warning("No assessments scraped")
                return []

            logger.info(f"Got {len(assessments)} assessments")

            # Step 2: Scrape details for each (optional, more time-consuming)
            # Commented out for efficiency - enable if you need full details
            # for assessment in assessments:
            #     details = self.scrape_assessment_details(assessment["url"])
            #     assessment.update(details)

            # Step 3: Deduplicate
            seen_urls = set()
            unique = []
            duplicates = 0

            for assessment in assessments:
                url = assessment.get("url", "").lower()
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique.append(assessment)
                else:
                    duplicates += 1

            logger.info(f"Removed {duplicates} duplicates")

            self.assessments = unique

            logger.info("=" * 80)
            logger.info(f"SCRAPE COMPLETE: {len(unique)} assessments")
            logger.info("=" * 80)

            return unique

        except Exception as e:
            logger.error(f"Scrape failed: {e}", exc_info=True)
            return []

    def save_catalog(self, output_path: str) -> None:
        """Save scraped catalog to JSON."""

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(
                    {
                        "assessments": self.assessments,
                        "count": len(self.assessments),
                        "scraped_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )

            logger.info(f"Saved {len(self.assessments)} assessments to {output_path}")

        except Exception as e:
            logger.error(f"Error saving catalog: {e}")
            raise


if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 80)
    print("SHL CATALOG SCRAPER")
    print("=" * 80)
    print("\nNOTE: This is a production-grade template.")
    print("Before using on live data:")
    print("1. Review SHL's Terms of Service")
    print("2. Obtain necessary permissions")
    print("3. Respect rate limiting")
    print("\nFor now, you can use: data/raw/catalog.json")
    print("=" * 80 + "\n")

    try:
        scraper = SHLScraper(use_cache=True)

        # Uncomment to run (requires authorization):
        # assessments = scraper.scrape_full_catalog()
        # scraper.save_catalog("data/raw/catalog.json")

        print("✓ Scraper initialized and ready")
        print("✓ Use data/raw/catalog.json for pipeline testing")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
