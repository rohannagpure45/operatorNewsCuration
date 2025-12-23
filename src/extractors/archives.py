"""Alternative archive services for bypassing paywalls."""

import asyncio
import logging
import random
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urlparse

import httpx
import trafilatura

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType

logger = logging.getLogger(__name__)


class ArchiveExtractor(BaseExtractor):
    """
    Extract content from alternative archive services.
    
    Supports:
    - archive.today (archive.is, archive.ph) - Often captures paywalled content
    - Google Cache - Recently indexed pages
    """

    url_type = URLType.NEWS_ARTICLE
    extraction_method = "archive_service"

    # Archive.today domains (reduced to avoid rate limiting)
    # Previously had 4 domains, now limited to 2 primary ones
    ARCHIVE_TODAY_DOMAINS = [
        "archive.today",
        "archive.is",
    ]
    
    # Backoff configuration
    BACKOFF_BASE_DELAY = 1.0  # seconds
    BACKOFF_MAX_DELAY = 30.0  # seconds
    BACKOFF_JITTER = 0.5  # seconds

    def __init__(self, timeout: int = 30):
        """Initialize the archive extractor."""
        super().__init__(timeout)

    def can_handle(self, url: str) -> bool:
        """Archive extractor can handle any HTTP(S) URL."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    async def extract(self, url: str) -> ExtractedContent:
        """
        Try to extract content from archive services.
        
        Tries in order:
        1. archive.today
        2. Google Cache
        """
        # Try archive.today first
        try:
            return await self.extract_from_archive_today(url)
        except ExtractionError as e:
            logger.debug(f"archive.today failed for {url}: {e}")

        # Try Google Cache
        try:
            return await self.extract_from_google_cache(url)
        except ExtractionError as e:
            logger.debug(f"Google Cache failed for {url}: {e}")

        raise ExtractionError(
            f"No archived version found in archive.today or Google Cache: {url}"
        )

    async def extract_from_archive_today(self, url: str) -> ExtractedContent:
        """
        Extract content from archive.today.
        
        archive.today often captures paywalled content because it saves
        the page before JavaScript paywalls activate.
        """
        logger.info(f"Trying archive.today for: {url}")

        client = await self.get_client()
        encoded_url = quote(url, safe="")

        # Try multiple archive.today domains
        for domain in self.ARCHIVE_TODAY_DOMAINS:
            try:
                # First, check if there's an archived version
                search_url = f"https://{domain}/newest/{encoded_url}"
                
                response = await client.get(
                    search_url,
                    follow_redirects=True,
                    timeout=self.timeout,
                )

                # If we get redirected to an archive page, we found it
                if response.status_code == 200:
                    final_url = str(response.url)
                    
                    # Check if we actually got an archived page (not a "not found" page)
                    if self._is_valid_archive_page(response.text, domain):
                        html = response.text
                        
                        # Clean archive.today specific elements
                        html = self._clean_archive_today_html(html)
                        
                        # Extract content
                        text = trafilatura.extract(
                            html,
                            url=url,
                            include_comments=False,
                            include_tables=True,
                        )

                        if text and len(text.strip()) >= 100:
                            metadata = trafilatura.extract_metadata(html, default_url=url)
                            
                            content = self._create_content(
                                url=url,
                                raw_text=text,
                                title=metadata.title if metadata else None,
                                author=metadata.author if metadata else None,
                                published_date=self._parse_metadata_date(metadata),
                                site_name=metadata.sitename if metadata else None,
                                fallback_used=True,
                            )
                            content.extraction_method = "archive_today"
                            return content

            except httpx.TimeoutException:
                logger.debug(f"Timeout accessing {domain}")
                continue
            except Exception as e:
                logger.debug(f"Error accessing {domain}: {e}")
                continue

        raise ExtractionError(f"No archive.today snapshot found for: {url}")

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.
        
        Args:
            attempt: The attempt number (0-indexed).
            
        Returns:
            Delay in seconds before the next attempt.
        """
        # Exponential backoff: base * 2^attempt
        delay = self.BACKOFF_BASE_DELAY * (2 ** attempt)
        
        # Add random jitter to prevent thundering herd
        jitter = random.uniform(0, self.BACKOFF_JITTER)
        delay += jitter
        
        # Cap at maximum delay
        return min(delay, self.BACKOFF_MAX_DELAY)

    async def extract_from_archive_today_with_backoff(
        self,
        url: str,
        max_retries: int = 3,
    ) -> ExtractedContent:
        """
        Extract from archive.today with exponential backoff on rate limiting.
        
        Tries all mirror domains before backing off. Only applies backoff
        when ALL domains have been tried and at least one returned 429.
        
        Args:
            url: The URL to find in archives.
            max_retries: Maximum number of retry attempts on 429 errors.
            
        Returns:
            ExtractedContent from the archive.
            
        Raises:
            ExtractionError: If all attempts fail.
        """
        logger.info(f"Trying archive.today with backoff for: {url}")
        
        client = await self.get_client()
        encoded_url = quote(url, safe="")
        
        for attempt in range(max_retries + 1):
            rate_limited_this_round = False
            
            # Try each domain
            for domain in self.ARCHIVE_TODAY_DOMAINS:
                try:
                    search_url = f"https://{domain}/newest/{encoded_url}"
                    
                    response = await client.get(
                        search_url,
                        follow_redirects=True,
                        timeout=self.timeout,
                    )
                    
                    # Handle rate limiting - continue to next domain instead of breaking
                    if response.status_code == 429:
                        logger.warning(f"Rate limited by {domain}, trying next mirror...")
                        rate_limited_this_round = True
                        continue  # Try next domain instead of breaking
                    
                    if response.status_code == 200:
                        final_url = str(response.url)
                        
                        if self._is_valid_archive_page(response.text, domain):
                            html = response.text
                            html = self._clean_archive_today_html(html)
                            
                            text = trafilatura.extract(
                                html,
                                url=url,
                                include_comments=False,
                                include_tables=True,
                            )
                            
                            if text and len(text.strip()) >= 100:
                                metadata = trafilatura.extract_metadata(html, default_url=url)
                                
                                content = self._create_content(
                                    url=url,
                                    raw_text=text,
                                    title=metadata.title if metadata else None,
                                    author=metadata.author if metadata else None,
                                    published_date=self._parse_metadata_date(metadata),
                                    site_name=metadata.sitename if metadata else None,
                                    fallback_used=True,
                                )
                                content.extraction_method = "archive_today"
                                return content
                    
                except httpx.TimeoutException:
                    logger.debug(f"Timeout accessing {domain}")
                    continue
                except ExtractionError:
                    raise
                except Exception as e:
                    logger.debug(f"Error accessing {domain}: {e}")
                    continue
            
            # After trying all domains, check if we should retry with backoff
            if rate_limited_this_round:
                if attempt < max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.warning(
                        f"All domains rate limited, backing off for {delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue  # Retry all domains
                else:
                    raise ExtractionError(
                        f"Rate limited by archive.today after {max_retries + 1} attempts: {url}"
                    )
            else:
                # No rate limiting encountered, no point retrying
                break
        
        raise ExtractionError(f"No archive.today snapshot found for: {url}")

    async def extract_from_google_cache(self, url: str) -> ExtractedContent:
        """
        Extract content from Google's cache.
        
        Google Cache is useful for recently indexed pages that may
        have been captured before paywall detection.
        """
        logger.info(f"Trying Google Cache for: {url}")

        client = await self.get_client()
        
        # Google Cache URL format
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote(url, safe='')}"

        try:
            response = await client.get(
                cache_url,
                follow_redirects=True,
                timeout=self.timeout,
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

            if response.status_code == 404:
                raise ExtractionError(f"No Google Cache found for: {url}")

            if response.status_code != 200:
                raise ExtractionError(
                    f"Google Cache returned status {response.status_code}"
                )

            html = response.text

            # Check if this is actually cached content (not an error page)
            if "cache:" not in str(response.url) and "webcache" not in str(response.url):
                raise ExtractionError("Google Cache redirected away from cache")

            # Check for redirect/error page indicators before extraction
            if not self._is_valid_google_cache_response(html, url):
                raise ExtractionError(
                    f"Google Cache returned redirect page, not cached content: {url}"
                )

            # Clean Google Cache specific elements
            html = self._clean_google_cache_html(html)

            # Extract content
            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
            )

            if not text or len(text.strip()) < 100:
                raise ExtractionError(
                    f"Could not extract meaningful content from Google Cache: {url}"
                )

            metadata = trafilatura.extract_metadata(html, default_url=url)

            # Post-extraction validation: check if title indicates error page
            if metadata and metadata.title:
                title_lower = metadata.title.lower()
                if "google search" in title_lower or (
                    "redirected" in title_lower and "google" in title_lower
                ):
                    raise ExtractionError(
                        f"Extracted content appears to be Google error page, not cached content: {url}"
                    )

            content = self._create_content(
                url=url,
                raw_text=text,
                title=metadata.title if metadata else None,
                author=metadata.author if metadata else None,
                published_date=self._parse_metadata_date(metadata),
                site_name=metadata.sitename if metadata else None,
                fallback_used=True,
            )
            content.extraction_method = "google_cache"
            return content

        except ExtractionError:
            raise
        except httpx.TimeoutException:
            raise ExtractionError(f"Google Cache request timed out for: {url}")
        except Exception as e:
            raise ExtractionError(f"Google Cache extraction failed: {e}")

    def _is_valid_archive_page(self, html: str, domain: str) -> bool:
        """Check if the HTML is a valid archived page, not a 'not found' page."""
        # archive.today shows a search form when no archive exists
        if "No results" in html or "0 results" in html:
            return False
        if f'action="https://{domain}/submit/"' in html:
            # This is the submission form, not an archived page
            if 'id="CONTENT"' not in html:
                return False
        return True

    def _is_valid_google_cache_response(self, html: str, original_url: str) -> bool:
        """
        Check if Google Cache response contains actual cached content.
        
        When Google Cache doesn't have a cached version of a page, it returns
        a redirect/error page instead of cached content. This method detects
        those invalid responses.
        
        Args:
            html: The HTML content from Google Cache response.
            original_url: The original URL we're trying to get from cache.
            
        Returns:
            True if the response appears to be valid cached content,
            False if it appears to be a redirect/error page.
        """
        # Reject redirect/error page indicators
        error_indicators = [
            "Please click here if you are not redirected",
            "you are not redirected within a few seconds",
            "having trouble accessing Google Search",
        ]
        for indicator in error_indicators:
            if indicator in html:
                logger.debug(f"Google Cache redirect indicator found: {indicator[:50]}...")
                return False
        return True

    def _clean_archive_today_html(self, html: str) -> str:
        """Remove archive.today specific elements from HTML."""
        # Remove archive.today toolbar/banner
        html = re.sub(
            r'<div[^>]*id="HEADER"[^>]*>.*?</div>',
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        
        # Remove archive.today scripts
        html = re.sub(
            r'<script[^>]*>.*?</script>',
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        return html

    def _clean_google_cache_html(self, html: str) -> str:
        """Remove Google Cache specific elements from HTML."""
        # Remove Google Cache header
        html = re.sub(
            r'<div[^>]*style="[^"]*background:#[^"]*Google[^"]*"[^>]*>.*?</div>',
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        
        # Remove "This is Google's cache" notice
        html = re.sub(
            r'<div[^>]*>.*?This is Google.*?cache.*?</div>',
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        return html

    def _parse_metadata_date(self, metadata) -> Optional[datetime]:
        """Parse date from trafilatura metadata."""
        if not metadata or not metadata.date:
            return None
        
        try:
            return datetime.fromisoformat(metadata.date)
        except ValueError:
            for fmt in ["%Y-%m-%d", "%B %d, %Y", "%d %B %Y"]:
                try:
                    return datetime.strptime(metadata.date, fmt)
                except ValueError:
                    continue
        return None


async def extract_from_archives(
    url: str,
    timeout: int = 30,
) -> ExtractedContent:
    """
    Convenience function to extract content from archive services.
    
    Args:
        url: The URL to find in archives.
        timeout: Request timeout in seconds.
        
    Returns:
        ExtractedContent from the first successful archive.
    """
    extractor = ArchiveExtractor(timeout=timeout)
    try:
        return await extractor.extract(url)
    finally:
        await extractor.close()

