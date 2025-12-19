"""Article content extractor using Trafilatura."""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import trafilatura
from trafilatura.settings import use_config

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType


class ArticleExtractor(BaseExtractor):
    """
    Extract content from news articles and blog posts using Trafilatura.
    
    Trafilatura achieves F1 score of 0.937 on content extraction benchmarks,
    making it one of the most accurate extraction libraries available.
    """

    url_type = URLType.NEWS_ARTICLE
    extraction_method = "trafilatura"

    def __init__(self, timeout: int = 30):
        """Initialize the extractor with Trafilatura configuration."""
        super().__init__(timeout)

        # Configure Trafilatura for best extraction
        self.config = use_config()
        self.config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(timeout))
        self.config.set("DEFAULT", "MIN_OUTPUT_SIZE", "100")
        self.config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "100")

    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle the URL.
        
        ArticleExtractor is the default fallback and can handle most URLs.
        """
        # This extractor handles anything that isn't Twitter or SEC
        twitter_patterns = [
            r"^https?://(www\.)?(twitter|x)\.com/",
        ]
        sec_patterns = [
            r"^https?://(www\.)?sec\.gov/",
            r"^https?://(www\.)?13f\.info/",
        ]

        url_lower = url.lower()
        for pattern in twitter_patterns + sec_patterns:
            if re.match(pattern, url_lower):
                return False

        return True

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract article content using Trafilatura.

        Args:
            url: URL of the article to extract.

        Returns:
            ExtractedContent with article text and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        try:
            # Fetch the page
            client = await self.get_client()
            response = await client.get(url)

            if response.status_code != 200:
                raise ExtractionError(
                    f"Failed to fetch article (status {response.status_code}): {url}"
                )

            html = response.text

            # Extract content using Trafilatura
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=False,
                output_format="txt",
                config=self.config,
            )

            if not result or len(result.strip()) < 100:
                raise ExtractionError(
                    f"Could not extract meaningful content from: {url}"
                )

            # Extract metadata
            metadata = trafilatura.extract_metadata(html, url=url)

            return self._create_content_from_trafilatura(url, result, metadata)

        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Error extracting article: {e}") from e

    def _create_content_from_trafilatura(
        self,
        url: str,
        text: str,
        metadata: Optional[trafilatura.metadata.Document],
    ) -> ExtractedContent:
        """Create ExtractedContent from Trafilatura results."""
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
                    # Try common date formats
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

        # Detect if this is a blog
        url_type = self._detect_content_type(url, metadata)

        content = self._create_content(
            url=url,
            raw_text=text,
            title=title,
            author=author,
            published_date=published_date,
            site_name=site_name,
        )
        content.url_type = url_type

        return content

    def _detect_content_type(
        self,
        url: str,
        metadata: Optional[trafilatura.metadata.Document],
    ) -> URLType:
        """Detect if content is a news article or blog."""
        url_lower = url.lower()

        # Blog indicators in URL
        blog_patterns = [
            r"/blog/",
            r"\.blog\.",
            r"blog\.",
            r"\.substack\.com",
            r"\.medium\.com",
            r"medium\.com/@",
            r"\.ghost\.io",
            r"\.wordpress\.com",
            r"\.blogspot\.com",
        ]

        for pattern in blog_patterns:
            if re.search(pattern, url_lower):
                return URLType.BLOG

        return URLType.NEWS_ARTICLE
