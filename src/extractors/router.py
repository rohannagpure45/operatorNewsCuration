"""URL router for detecting URL types and dispatching to appropriate extractors."""

import re
from typing import Optional
from urllib.parse import urlparse

from src.models.schemas import URLType


class URLRouter:
    """Routes URLs to appropriate extractors based on URL patterns."""

    # Twitter/X URL patterns (handles any subdomain: www, mobile, m, etc.)
    TWITTER_PATTERNS = [
        r"^https?://([^/]*\.)?(twitter|x)\.com/\w+/status/\d+",
        r"^https?://([^/]*\.)?twitter\.com/\w+",
        r"^https?://([^/]*\.)?x\.com/\w+",
    ]

    # SEC filing patterns
    SEC_PATTERNS = [
        r"^https?://(www\.)?sec\.gov/",
        r"^https?://(www\.)?13f\.info/",
        r"^https?://(www\.)?secfilings\.nasdaq\.com/",
    ]

    # Known blog platforms/patterns
    BLOG_PATTERNS = [
        r"^https?://[^/]*\.substack\.com/",
        r"^https?://[^/]*\.medium\.com/",
        r"^https?://medium\.com/",
        r"^https?://[^/]*\.ghost\.io/",
        r"^https?://[^/]*\.wordpress\.com/",
        r"^https?://[^/]*\.blogspot\.com/",
        r"^https?://blog\.[^/]+/",
        r"^https?://[^/]+/blog/",
    ]

    # Known news domains
    NEWS_DOMAINS = {
        "bloomberg.com",
        "wsj.com",
        "nytimes.com",
        "washingtonpost.com",
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "bbc.co.uk",
        "cnn.com",
        "theguardian.com",
        "economist.com",
        "ft.com",
        "forbes.com",
        "businessinsider.com",
        "cnbc.com",
        "techcrunch.com",
        "wired.com",
        "arstechnica.com",
        "theverge.com",
        "engadget.com",
        "wccftech.com",
        "tomshardware.com",
        "anandtech.com",
    }

    @classmethod
    def detect_url_type(cls, url: str) -> URLType:
        """
        Detect the type of URL based on patterns and domain.

        Args:
            url: The URL to analyze.

        Returns:
            URLType enum value indicating the type of content.
        """
        url_lower = url.lower()

        # Check Twitter/X
        for pattern in cls.TWITTER_PATTERNS:
            if re.match(pattern, url_lower):
                return URLType.TWITTER

        # Check SEC filings
        for pattern in cls.SEC_PATTERNS:
            if re.match(pattern, url_lower):
                return URLType.SEC_FILING

        # Check blogs
        for pattern in cls.BLOG_PATTERNS:
            if re.match(pattern, url_lower):
                return URLType.BLOG

        # Check known news domains
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]

            if domain in cls.NEWS_DOMAINS:
                return URLType.NEWS_ARTICLE

            # Check if domain is a subdomain of any known news domain
            for news_domain in cls.NEWS_DOMAINS:
                if domain == news_domain or domain.endswith(f".{news_domain}"):
                    return URLType.NEWS_ARTICLE

        except Exception:
            pass

        # Default to news article for general URLs
        # The article extractor (Trafilatura) handles most web content well
        return URLType.NEWS_ARTICLE

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """
        Check if a URL is valid and supported.

        Args:
            url: The URL to validate.

        Returns:
            True if the URL is valid and can be processed.
        """
        try:
            parsed = urlparse(url)
            return all([parsed.scheme in ("http", "https"), parsed.netloc])
        except Exception:
            return False

    @classmethod
    def extract_tweet_id(cls, url: str) -> Optional[str]:
        """
        Extract tweet ID from a Twitter/X URL.

        Args:
            url: Twitter/X URL.

        Returns:
            Tweet ID string or None if not found.
        """
        match = re.search(r"/status/(\d+)", url)
        return match.group(1) if match else None

    @classmethod
    def normalize_url(cls, url: str) -> str:
        """
        Normalize a URL for consistent handling.

        Args:
            url: The URL to normalize.

        Returns:
            Normalized URL string.
        """
        # Ensure URL has a scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Parse and reconstruct to normalize
        parsed = urlparse(url)

        # Remove trailing slashes from path (except for root)
        path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path

        # Reconstruct URL
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"

        return normalized


