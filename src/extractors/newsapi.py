"""NewsAPI integration for article summary fallback."""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx

from src.config import get_settings
from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType

logger = logging.getLogger(__name__)

# NewsAPI endpoint
NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"


class NewsAPIExtractor(BaseExtractor):
    """
    Extract article summaries from NewsAPI.org.
    
    NewsAPI aggregates articles from 150,000+ sources and can be used
    as a fallback when direct extraction fails. Note that NewsAPI only
    provides article summaries/descriptions, not full content.
    
    Free tier: 500 requests/day
    """

    url_type = URLType.NEWS_ARTICLE
    extraction_method = "newsapi"

    def __init__(self, timeout: int = 30, api_key: Optional[str] = None):
        """
        Initialize the NewsAPI extractor.
        
        Args:
            timeout: Request timeout in seconds.
            api_key: NewsAPI API key. If not provided, reads from settings.
        """
        super().__init__(timeout)
        settings = get_settings()
        self._api_key = api_key or getattr(settings, 'newsapi_key', None)

    @property
    def is_configured(self) -> bool:
        """Check if NewsAPI is configured with an API key."""
        return bool(self._api_key)

    def can_handle(self, url: str) -> bool:
        """NewsAPI can handle any news article URL."""
        return True

    async def search_by_url(self, url: str) -> Optional[dict]:
        """
        Search for an article by its URL in NewsAPI.
        
        Args:
            url: The article URL to search for.
            
        Returns:
            Article dict from NewsAPI or None if not found.
        """
        if not self._api_key:
            return None

        try:
            # Extract domain for filtering
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")

            client = await self.get_client()
            
            # Search by domain
            response = await client.get(
                NEWSAPI_EVERYTHING_URL,
                params={
                    "apiKey": self._api_key,
                    "domains": domain,
                    "pageSize": 10,
                    "sortBy": "publishedAt",
                },
                timeout=self.timeout,
            )

            if response.status_code != 200:
                logger.debug(f"NewsAPI returned status {response.status_code}")
                return None

            data = response.json()
            articles = data.get("articles", [])

            # Find matching article by URL
            for article in articles:
                article_url = article.get("url", "")
                if self._urls_match(url, article_url):
                    return article

            return None

        except Exception as e:
            logger.debug(f"NewsAPI search failed: {e}")
            return None

    async def search_by_title(
        self,
        title: str,
        domain: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Search for an article by title.
        
        Args:
            title: The article title to search for.
            domain: Optional domain to filter by.
            
        Returns:
            Best matching article dict or None.
        """
        if not self._api_key:
            return None

        try:
            client = await self.get_client()
            
            params = {
                "apiKey": self._api_key,
                "q": f'"{title}"',
                "pageSize": 5,
                "sortBy": "relevancy",
            }
            
            if domain:
                params["domains"] = domain

            response = await client.get(
                NEWSAPI_EVERYTHING_URL,
                params=params,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            articles = data.get("articles", [])

            if articles:
                return articles[0]

            return None

        except Exception as e:
            logger.debug(f"NewsAPI title search failed: {e}")
            return None

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract article summary from NewsAPI.
        
        Args:
            url: The article URL to search for.
            
        Returns:
            ExtractedContent with the article summary.
            
        Raises:
            ExtractionError: If the article cannot be found.
        """
        if not self._api_key:
            raise ExtractionError(
                "NewsAPI not configured. Set NEWSAPI_KEY in your environment."
            )

        logger.info(f"Searching NewsAPI for: {url}")

        # Try to find the article by URL
        article = await self.search_by_url(url)

        if not article:
            raise ExtractionError(
                f"Article not found in NewsAPI: {url}"
            )

        return self._create_content_from_article(url, article)

    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs refer to the same article."""
        # Normalize URLs for comparison
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)

        # Compare paths (ignore trailing slashes)
        path1 = parsed1.path.rstrip("/")
        path2 = parsed2.path.rstrip("/")

        return path1 == path2

    def _create_content_from_article(
        self,
        original_url: str,
        article: dict,
    ) -> ExtractedContent:
        """Create ExtractedContent from NewsAPI article."""
        title = article.get("title", "")
        author = article.get("author")
        
        # Combine description and content for more text
        description = article.get("description", "") or ""
        content = article.get("content", "") or ""
        
        # NewsAPI truncates content with "[+N chars]", remove that
        if content and "[+" in content:
            content = content.split("[+")[0]
        
        raw_text = f"{description}\n\n{content}".strip()
        
        if not raw_text:
            raise ExtractionError("NewsAPI article has no content")

        # Parse published date
        published_date = None
        published_at = article.get("publishedAt")
        if published_at:
            try:
                published_date = datetime.fromisoformat(
                    published_at.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Get source name
        source = article.get("source", {})
        site_name = source.get("name")

        content = self._create_content(
            url=original_url,
            raw_text=raw_text,
            title=title,
            author=author,
            published_date=published_date,
            site_name=site_name,
            fallback_used=True,
        )
        content.extraction_method = "newsapi"
        
        return content


async def search_newsapi(
    url: str,
    api_key: Optional[str] = None,
) -> Optional[ExtractedContent]:
    """
    Convenience function to search for an article in NewsAPI.
    
    Args:
        url: The article URL to search for.
        api_key: Optional API key (uses settings if not provided).
        
    Returns:
        ExtractedContent if found, None otherwise.
    """
    extractor = NewsAPIExtractor(api_key=api_key)
    
    if not extractor.is_configured:
        return None
    
    try:
        return await extractor.extract(url)
    except ExtractionError:
        return None
    finally:
        await extractor.close()

