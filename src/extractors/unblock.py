"""Unblock extractor using Browserless /unblock API for bot detection bypass."""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx
import trafilatura

from src.config import get_settings
from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType

logger = logging.getLogger(__name__)

# Browserless API endpoint
BROWSERLESS_UNBLOCK_URL = "https://production-sfo.browserless.io/unblock"

# Default retry settings
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_DELAY = 1.0  # seconds


class UnblockExtractor(BaseExtractor):
    """
    Extract content using Browserless /unblock API.
    
    The /unblock API is designed to bypass bot detection mechanisms
    like Datadome and passive CAPTCHAs. It provides better success rates
    for sites with aggressive anti-automation measures.
    
    This extractor is intended as a fallback when the standard browser
    extractor fails due to bot detection.
    """

    url_type = URLType.NEWS_ARTICLE
    extraction_method = "browserless_unblock"

    def __init__(self, timeout: Optional[int] = None):
        """
        Initialize the unblock extractor.
        
        Args:
            timeout: Request timeout in seconds. If not provided,
                     uses extraction_timeout from settings.
        """
        settings = get_settings()
        timeout = timeout or settings.extraction_timeout
        super().__init__(timeout)
        
        self._api_key = settings.browserless_api_key
        self._use_residential_proxy = getattr(
            settings, 'browserless_use_residential_proxy', False
        )

    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle the URL.
        
        UnblockExtractor can handle any HTTP(S) URL.
        """
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    async def fetch_content(
        self,
        url: str,
        wait_for_timeout: Optional[int] = None,
        wait_for_selector: Optional[str] = None,
    ) -> str:
        """
        Fetch rendered HTML content using the /unblock API.
        
        Args:
            url: URL to fetch content from.
            wait_for_timeout: Optional milliseconds to wait before scraping.
            wait_for_selector: Optional CSS selector to wait for before scraping.
            
        Returns:
            Rendered HTML content as string.
            
        Raises:
            ExtractionError: If the API call fails or returns no content.
        """
        if not self._api_key:
            raise ExtractionError(
                "Browserless API key not configured. "
                "Set BROWSERLESS_API_KEY environment variable."
            )

        try:
            client = await self.get_client()
            
            # Build the API endpoint URL with token
            endpoint = f"{BROWSERLESS_UNBLOCK_URL}?token={self._api_key}"
            
            # Add residential proxy if configured
            if self._use_residential_proxy:
                endpoint += "&proxy=residential"
            
            # Request payload - we want HTML content back
            payload = {
                "url": url,
                "content": True,
            }
            
            # Add optional waitFor options
            if wait_for_timeout is not None:
                payload["waitForTimeout"] = wait_for_timeout
            
            if wait_for_selector is not None:
                payload["waitForSelector"] = {"selector": wait_for_selector}
            
            response = await client.post(
                endpoint,
                json=payload,
                timeout=self.timeout,
            )
            
            # Handle HTTP errors
            if response.status_code >= 400:
                raise ExtractionError(
                    f"Unblock API returned status {response.status_code}: {response.text}"
                )
            
            # Parse response
            data = response.json()
            content = data.get("content")
            
            if not content:
                raise ExtractionError(
                    f"Unblock API returned empty content for: {url}"
                )
            
            return content
            
        except httpx.TimeoutException:
            raise ExtractionError(
                f"Unblock API request timed out for: {url}"
            ) from None
        except httpx.ConnectError as e:
            raise ExtractionError(
                f"Unblock API request failed: Connection refused"
            ) from None
        except httpx.HTTPError as e:
            # Sanitize error message to avoid leaking API key
            error_str = str(e)
            if self._api_key and self._api_key in error_str:
                error_str = error_str.replace(self._api_key, "[REDACTED]")
            raise ExtractionError(
                f"Unblock API request failed: {error_str}"
            ) from None
        except ExtractionError:
            raise
        except Exception as e:
            # Catch-all for unexpected errors, sanitize API key
            error_str = str(e)
            if self._api_key and self._api_key in error_str:
                error_str = error_str.replace(self._api_key, "[REDACTED]")
            raise ExtractionError(
                f"Unblock API error: {error_str}"
            ) from None

    async def fetch_content_with_retry(
        self,
        url: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        wait_for_timeout: Optional[int] = None,
        wait_for_selector: Optional[str] = None,
    ) -> str:
        """
        Fetch content with automatic retry on transient failures.
        
        Retries on:
        - 5xx server errors
        - Timeout errors
        - Connection errors
        
        Does NOT retry on:
        - 4xx client errors (indicates a problem with the request)
        - Empty content responses
        
        Args:
            url: URL to fetch content from.
            max_retries: Maximum number of retry attempts.
            retry_delay: Base delay between retries (exponential backoff).
            wait_for_timeout: Optional milliseconds to wait before scraping.
            wait_for_selector: Optional CSS selector to wait for before scraping.
            
        Returns:
            Rendered HTML content as string.
            
        Raises:
            ExtractionError: If all retry attempts fail.
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.fetch_content(
                    url,
                    wait_for_timeout=wait_for_timeout,
                    wait_for_selector=wait_for_selector,
                )
            except ExtractionError as e:
                error_str = str(e).lower()
                
                # Don't retry on 4xx errors - these are client errors
                if "status 4" in error_str:
                    raise
                
                # Retry on 5xx errors, timeouts, and connection errors
                is_retryable = (
                    "status 5" in error_str
                    or "timed out" in error_str
                    or "connection" in error_str
                )
                
                if is_retryable and attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Unblock API attempt {attempt + 1} failed for {url}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    last_error = e
                else:
                    raise
        
        # Should not reach here, but just in case
        raise last_error or ExtractionError(f"Failed to fetch content from: {url}")

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract content using the /unblock API and parse with trafilatura.
        
        Args:
            url: URL to extract content from.
            
        Returns:
            ExtractedContent with parsed article text and metadata.
            
        Raises:
            ExtractionError: If extraction fails.
        """
        # Fetch the rendered HTML with automatic retry on transient failures
        html = await self.fetch_content_with_retry(url)
        
        # Parse with trafilatura
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_links=False,
            output_format="txt",
        )
        
        if not text or len(text.strip()) < 100:
            raise ExtractionError(
                f"Could not extract meaningful content from: {url}"
            )
        
        # Extract metadata
        metadata = trafilatura.extract_metadata(html, default_url=url)
        
        return self._create_content_from_unblock(url, text, metadata)

    def _create_content_from_unblock(
        self,
        url: str,
        text: str,
        metadata: Optional[trafilatura.metadata.Document],
    ) -> ExtractedContent:
        """Create ExtractedContent from unblock extraction results."""
        title = None
        author = None
        published_date = None
        site_name = None

        if metadata:
            title = metadata.title
            author = metadata.author
            site_name = metadata.sitename

            # Parse date
            if metadata.date:
                try:
                    published_date = datetime.fromisoformat(metadata.date)
                except ValueError:
                    for fmt in ["%Y-%m-%d", "%B %d, %Y", "%d %B %Y"]:
                        try:
                            published_date = datetime.strptime(metadata.date, fmt)
                            break
                        except ValueError:
                            continue

        # Fallback for site name
        if not site_name:
            try:
                parsed = urlparse(url)
                site_name = parsed.netloc.replace("www.", "")
            except Exception:
                pass

        return self._create_content(
            url=url,
            raw_text=text,
            title=title,
            author=author,
            published_date=published_date,
            site_name=site_name,
            fallback_used=True,  # Unblock is always a fallback method
        )
