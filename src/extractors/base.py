"""Base extractor interface and common utilities."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.models.schemas import (
    ContentMetadata,
    ExtractedContent,
    URLType,
)


class ExtractionError(Exception):
    """Raised when content extraction fails."""

    pass


class BaseExtractor(ABC):
    """Abstract base class for content extractors."""

    url_type: URLType = URLType.UNKNOWN
    extraction_method: str = "base"

    def __init__(self, timeout: int = 30):
        """Initialize the extractor with a timeout."""
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract content from the given URL.

        Args:
            url: The URL to extract content from.

        Returns:
            ExtractedContent with the extracted text and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle the given URL.

        Args:
            url: The URL to check.

        Returns:
            True if this extractor can handle the URL, False otherwise.
        """
        pass

    def _create_content(
        self,
        url: str,
        raw_text: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        published_date: Optional[datetime] = None,
        site_name: Optional[str] = None,
        language: str = "en",
        fallback_used: bool = False,
    ) -> ExtractedContent:
        """Create an ExtractedContent object with common fields."""
        word_count = len(raw_text.split()) if raw_text else 0

        return ExtractedContent(
            url=url,
            url_type=self.url_type,
            raw_text=raw_text,
            metadata=ContentMetadata(
                title=title,
                author=author,
                published_date=published_date,
                word_count=word_count,
                language=language,
                site_name=site_name,
            ),
            extracted_at=datetime.now(timezone.utc),
            extraction_method=self.extraction_method,
            fallback_used=fallback_used,
        )

