"""RSS/Atom feed extractor for sites with bot protection but available feeds."""

import html
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType

logger = logging.getLogger(__name__)


class RSSExtractor(BaseExtractor):
    """
    Extract content from RSS/Atom feeds as a fallback for bot-protected sites.
    
    This extractor is useful for sites like OpenAI and Anthropic that block
    direct access but provide RSS feeds with full article content.
    """

    url_type = URLType.BLOG
    extraction_method = "rss_feed"

    def __init__(self, timeout: int = 30):
        """Initialize the RSS extractor."""
        super().__init__(timeout)

    def can_handle(self, url: str) -> bool:
        """RSS extractor handles any URL if we have an RSS feed for the domain."""
        return True

    async def extract_from_feed(
        self,
        article_url: str,
        feed_url: str,
    ) -> ExtractedContent:
        """
        Extract article content by finding it in an RSS feed.
        
        Args:
            article_url: The original article URL that failed to load.
            feed_url: The RSS/Atom feed URL to search.
            
        Returns:
            ExtractedContent with the article text and metadata.
            
        Raises:
            ExtractionError: If the article cannot be found or extracted.
        """
        try:
            # Import feedparser here to make it optional
            import feedparser
        except ImportError:
            raise ExtractionError(
                "feedparser not installed. Run: pip install feedparser"
            )

        logger.info(f"Fetching RSS feed: {feed_url}")

        try:
            client = await self.get_client()
            response = await client.get(feed_url)

            if response.status_code != 200:
                raise ExtractionError(
                    f"Failed to fetch RSS feed (status {response.status_code}): {feed_url}"
                )

            # Parse the feed
            feed = feedparser.parse(response.text)

            if feed.bozo and not feed.entries:
                raise ExtractionError(f"Invalid RSS feed: {feed_url}")

            # Find the matching entry
            entry, match_score = self._find_matching_entry(
                article_url, feed.entries
            )

            if not entry:
                raise ExtractionError(
                    f"Article not found in RSS feed. URL: {article_url}"
                )

            logger.info(
                f"Found matching RSS entry: {entry.get('title', 'Untitled')} "
                f"(match score: {match_score:.2f})"
            )

            # Extract content from the entry
            return self._create_content_from_entry(
                original_url=article_url,
                entry=entry,
                feed=feed,
            )

        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"RSS extraction failed: {e}") from e

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract content from URL (not directly supported - use extract_from_feed).
        
        This method exists for interface compatibility but RSS extraction
        requires knowing the feed URL, so use extract_from_feed() directly.
        """
        raise ExtractionError(
            "RSS extractor requires a feed URL. Use extract_from_feed() instead."
        )

    def _find_matching_entry(
        self,
        article_url: str,
        entries: List,
    ) -> Tuple[Optional[dict], float]:
        """
        Find the RSS entry that matches the article URL.
        
        Uses multiple matching strategies:
        1. Exact URL match
        2. URL path match (ignoring query params)
        3. Slug match from URL path
        4. Title similarity (for redirected URLs)
        
        Returns:
            Tuple of (matching entry, confidence score 0-1) or (None, 0).
        """
        if not entries:
            return None, 0.0

        article_parsed = urlparse(article_url)
        article_path = article_parsed.path.rstrip("/").lower()
        article_slug = self._extract_slug(article_path)

        best_match = None
        best_score = 0.0

        for entry in entries:
            entry_url = entry.get("link", "")
            entry_parsed = urlparse(entry_url)
            entry_path = entry_parsed.path.rstrip("/").lower()
            entry_slug = self._extract_slug(entry_path)

            # Strategy 1: Exact URL match
            if article_url.rstrip("/") == entry_url.rstrip("/"):
                return entry, 1.0

            # Strategy 2: Path match (ignoring domain differences)
            if article_path == entry_path:
                return entry, 0.95

            # Strategy 3: Slug match
            if article_slug and entry_slug:
                slug_similarity = SequenceMatcher(
                    None, article_slug, entry_slug
                ).ratio()
                if slug_similarity > 0.8 and slug_similarity > best_score:
                    best_match = entry
                    best_score = slug_similarity

            # Strategy 4: Check if article URL is contained in entry URL or vice versa
            # Only apply for slugs >= 4 chars to avoid false positives (e.g., "ai" matching "/training-ai/")
            if len(article_slug) >= 4 and len(entry_slug) >= 4:
                if article_slug in entry_path or entry_slug in article_path:
                    score = 0.7
                    if score > best_score:
                        best_match = entry
                        best_score = score

        # If we found a good match, return it
        if best_score >= 0.7:
            return best_match, best_score

        return None, 0.0

    def _extract_slug(self, path: str) -> str:
        """Extract the article slug from a URL path."""
        # Remove common prefixes
        path = re.sub(r"^/(index|blog|news|articles?|posts?)/", "/", path)
        
        # Get the last path component
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[-1]
        return ""

    def _create_content_from_entry(
        self,
        original_url: str,
        entry: dict,
        feed: dict,
    ) -> ExtractedContent:
        """Create ExtractedContent from an RSS entry."""
        # Get content - try multiple fields
        content = ""
        
        # Try content:encoded first (often has full HTML)
        # Defensive check: ensure content exists and has at least one element
        if "content" in entry and entry.content and len(entry.content) > 0:
            content = entry.content[0].get("value", "")
        
        # Fall back to summary/description
        if not content or len(content) < 200:
            content = entry.get("summary", "") or entry.get("description", "")

        # Clean HTML from content
        content = self._clean_html(content)

        if not content or len(content.strip()) < 50:
            raise ExtractionError(
                f"RSS entry has insufficient content: {entry.get('title', 'Untitled')}"
            )

        # Extract metadata
        title = entry.get("title", "").strip()
        author = self._get_author(entry)
        published_date = self._parse_date(entry)
        site_name = feed.feed.get("title", "") if hasattr(feed, "feed") else ""

        return self._create_content(
            url=original_url,
            raw_text=content,
            title=title,
            author=author,
            published_date=published_date,
            site_name=site_name,
            fallback_used=True,
        )

    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags and decode entities."""
        if not html_content:
            return ""

        # Decode HTML entities
        text = html.unescape(html_content)

        # Remove HTML tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _get_author(self, entry: dict) -> Optional[str]:
        """Extract author from RSS entry."""
        # Try author field
        if "author" in entry:
            return entry["author"]
        
        # Try author_detail
        if "author_detail" in entry:
            return entry["author_detail"].get("name")
        
        # Try authors list
        if "authors" in entry and entry["authors"]:
            names = [a.get("name", "") for a in entry["authors"] if a.get("name")]
            if names:
                return ", ".join(names)
        
        # Try dc:creator
        if "creator" in entry:
            return entry["creator"]

        return None

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse publication date from RSS entry."""
        # Try published_parsed (struct_time)
        if "published_parsed" in entry and entry["published_parsed"]:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(entry["published_parsed"]))
            except (ValueError, OverflowError):
                pass

        # Try updated_parsed
        if "updated_parsed" in entry and entry["updated_parsed"]:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(entry["updated_parsed"]))
            except (ValueError, OverflowError):
                pass

        # Try parsing string dates
        for field in ["published", "updated", "date"]:
            if field in entry and entry[field]:
                try:
                    # Common date formats
                    for fmt in [
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%a, %d %b %Y %H:%M:%S %z",
                        "%a, %d %b %Y %H:%M:%S %Z",
                        "%Y-%m-%d",
                    ]:
                        try:
                            return datetime.strptime(entry[field], fmt)
                        except ValueError:
                            continue
                except Exception:
                    pass

        return None


async def extract_from_rss(
    article_url: str,
    feed_url: str,
    timeout: int = 30,
) -> ExtractedContent:
    """
    Convenience function to extract article content from an RSS feed.
    
    Args:
        article_url: The article URL that failed to load directly.
        feed_url: The RSS/Atom feed URL to search.
        timeout: Request timeout in seconds.
        
    Returns:
        ExtractedContent with the article text and metadata.
    """
    extractor = RSSExtractor(timeout=timeout)
    try:
        return await extractor.extract_from_feed(article_url, feed_url)
    finally:
        await extractor.close()

