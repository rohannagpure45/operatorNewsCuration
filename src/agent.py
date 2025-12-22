"""Main agent orchestrator that coordinates all components."""

import asyncio
import logging
import time
from typing import List, Optional

from src.config import get_settings
from src.enrichment.fact_check import FactChecker
from src.enrichment.wayback import WaybackFetcher
from src.extractors.archives import ArchiveExtractor
from src.extractors.article import ArticleExtractor
from src.extractors.base import ExtractionError
from src.extractors.browser import BrowserExtractor
from src.extractors.router import URLRouter
from src.extractors.rss import RSSExtractor
from src.extractors.sec_filings import SECExtractor
from src.extractors.site_hints import (
    get_error_message,
    get_rss_feed,
    get_site_hint,
    should_try_archive_today,
    should_try_google_cache,
)
from src.extractors.twitter import TwitterExtractor
from src.extractors.unblock import UnblockExtractor
from src.models.schemas import (
    ExtractedContent,
    FactCheckReport,
    ProcessedResult,
    ProcessingStatus,
    URLType,
)
from src.summarizer.llm import AsyncSummarizer, SummarizationError

logger = logging.getLogger(__name__)


class NewsAgent:
    """
    Autonomous agent for processing URLs into structured summaries.
    
    Orchestrates:
    1. URL type detection and routing
    2. Content extraction (with Wayback fallback)
    3. Fact-checking
    4. LLM summarization
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        fact_check_api_key: Optional[str] = None,
    ):
        """Initialize the agent with all required components."""
        settings = get_settings()

        # Initialize extractors
        self.twitter_extractor = TwitterExtractor(timeout=settings.extraction_timeout)
        self.article_extractor = ArticleExtractor(timeout=settings.extraction_timeout)
        self.sec_extractor = SECExtractor(timeout=settings.extraction_timeout)
        self.browser_extractor = BrowserExtractor(timeout=settings.extraction_timeout)
        self.unblock_extractor = UnblockExtractor(timeout=settings.extraction_timeout)
        self.rss_extractor = RSSExtractor(timeout=settings.extraction_timeout)
        self.archive_extractor = ArchiveExtractor(timeout=settings.extraction_timeout)
        
        # Check if unblock fallback is enabled
        self._use_unblock = getattr(settings, 'browserless_use_unblock', True)

        # Initialize enrichment components
        self.wayback = WaybackFetcher(timeout=settings.extraction_timeout)
        self.fact_checker = FactChecker(
            api_key=fact_check_api_key,
            timeout=settings.extraction_timeout,
        )

        # Initialize summarizer
        self.summarizer = AsyncSummarizer(api_key=gemini_api_key)

        # Configuration
        self.max_concurrent = settings.max_concurrent_requests

    async def close(self) -> None:
        """Close all HTTP clients and resources."""
        await asyncio.gather(
            self.twitter_extractor.close(),
            self.article_extractor.close(),
            self.sec_extractor.close(),
            self.browser_extractor.close(),
            self.unblock_extractor.close(),
            self.rss_extractor.close(),
            self.archive_extractor.close(),
            self.wayback.close(),
            self.fact_checker.close(),
            self.summarizer.close(),
        )

    async def process(
        self,
        url: str,
        skip_fact_check: bool = False,
        include_raw_text: bool = False,
    ) -> ProcessedResult:
        """
        Process a single URL through the full pipeline.

        Args:
            url: The URL to process.
            skip_fact_check: Skip the fact-checking step.
            include_raw_text: Include raw text in the result.

        Returns:
            ProcessedResult with summary and fact-check data.
        """
        start_time = time.time()

        # Validate and normalize URL
        if not URLRouter.is_valid_url(url):
            return ProcessedResult(
                url=url,
                source_type=URLType.UNKNOWN,
                status=ProcessingStatus.FAILED,
                error="Invalid URL format",
            )

        url = URLRouter.normalize_url(url)
        url_type = URLRouter.detect_url_type(url)

        result = ProcessedResult(
            url=url,
            source_type=url_type,
            status=ProcessingStatus.EXTRACTING,
        )

        try:
            # Check for known problematic sites and log a warning
            site_hint = get_site_hint(url)
            if site_hint:
                logger.warning(
                    f"Known problematic site detected: {site_hint.name} - {site_hint.issue}"
                )

            # Step 1: Extract content
            logger.info(f"Extracting content from: {url}")
            content = await self._extract_content(url, url_type)
            result.extracted_at = content.extracted_at
            result.content = content.metadata

            if include_raw_text:
                result.raw_text = content.raw_text

            # Step 2: Fact-check (optional)
            fact_check_report = None
            if not skip_fact_check:
                logger.info(f"Fact-checking content from: {url}")
                result.status = ProcessingStatus.FACT_CHECKING
                fact_check_report = await self._fact_check_content(content)
                result.fact_check = fact_check_report

            # Step 3: Summarize
            logger.info(f"Summarizing content from: {url}")
            result.status = ProcessingStatus.SUMMARIZING
            summary = await self.summarizer.summarize(content)
            result.summary = summary

            # Done!
            result.status = ProcessingStatus.COMPLETED
            result.processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Successfully processed {url} in {result.processing_time_ms}ms"
            )

        except ExtractionError as e:
            logger.error(f"Extraction failed for {url}: {e}")
            result.status = ProcessingStatus.FAILED
            # Use enhanced error message with site-specific hints
            error_msg = get_error_message(url, str(e))
            result.error = f"Extraction failed: {error_msg}"

        except SummarizationError as e:
            logger.error(f"Summarization failed for {url}: {e}")
            result.status = ProcessingStatus.FAILED
            result.error = f"Summarization failed: {e}"

        except Exception as e:
            logger.exception(f"Unexpected error processing {url}")
            result.status = ProcessingStatus.FAILED
            result.error = f"Unexpected error: {e}"

        return result

    async def process_batch(
        self,
        urls: List[str],
        skip_fact_check: bool = False,
        include_raw_text: bool = False,
        sequential: bool = True,
    ) -> List[ProcessedResult]:
        """
        Process multiple URLs.

        Args:
            urls: List of URLs to process.
            skip_fact_check: Skip fact-checking for all URLs.
            include_raw_text: Include raw text in results.
            sequential: Process URLs one at a time (default True to respect rate limits).

        Returns:
            List of ProcessedResult objects.
        """
        if sequential:
            # Process URLs one at a time to respect rate limits
            results = []
            for url in urls:
                result = await self.process(
                    url,
                    skip_fact_check=skip_fact_check,
                    include_raw_text=include_raw_text,
                )
                results.append(result)
            return results

        # Concurrent processing (use with caution on rate-limited APIs)
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_semaphore(url: str) -> ProcessedResult:
            async with semaphore:
                return await self.process(
                    url,
                    skip_fact_check=skip_fact_check,
                    include_raw_text=include_raw_text,
                )

        tasks = [process_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return list(results)

    async def _extract_content(
        self,
        url: str,
        url_type: URLType,
    ) -> ExtractedContent:
        """
        Extract content using the appropriate extractor with enhanced fallback chain.
        
        Fallback order:
        1. Primary extraction (httpx + trafilatura)
        2. RSS feed extraction (if available for site)
        3. Browser fallback (Playwright)
        4. Unblock API fallback (Browserless /unblock)
        5. archive.today (for paywalled sites)
        6. Google Cache (for paywalled sites)
        7. Wayback Machine (last resort)
        """
        # Select extractor based on URL type
        if url_type == URLType.TWITTER:
            extractor = self.twitter_extractor
        elif url_type == URLType.SEC_FILING:
            extractor = self.sec_extractor
        else:
            extractor = self.article_extractor

        try:
            content = await extractor.extract(url)
            return content

        except ExtractionError as primary_error:
            # For articles, try fallback chain
            if url_type not in (URLType.TWITTER, URLType.SEC_FILING):
                
                # Fallback 1: Try RSS feed if available
                rss_feed = get_rss_feed(url)
                if rss_feed:
                    logger.info(f"Trying RSS feed fallback for: {url}")
                    try:
                        content = await self.rss_extractor.extract_from_feed(
                            article_url=url,
                            feed_url=rss_feed,
                        )
                        logger.info(f"Successfully extracted from RSS feed: {rss_feed}")
                        return content
                    except ExtractionError as rss_error:
                        logger.warning(f"RSS fallback failed for {url}: {rss_error}")

                # Fallback 2: Try browser (may bypass bot detection or render JS)
                logger.info(f"Trying Playwright browser fallback for: {url}")
                try:
                    content = await self.browser_extractor.extract(url)
                    content.extraction_method = "playwright_browser"
                    return content
                except ExtractionError as browser_error:
                    logger.warning(
                        f"Browser fallback failed for {url}: {browser_error}"
                    )

                # Fallback 3: Try /unblock API (better bot detection bypass)
                if self._use_unblock:
                    logger.info(f"Trying Browserless /unblock API fallback for: {url}")
                    try:
                        content = await self.unblock_extractor.extract(url)
                        return content
                    except ExtractionError as unblock_error:
                        logger.warning(
                            f"Unblock API fallback failed for {url}: {unblock_error}"
                        )

                # Fallback 4: Try archive.today (good for paywalled content)
                if should_try_archive_today(url):
                    logger.info(f"Trying archive.today fallback for: {url}")
                    try:
                        content = await self.archive_extractor.extract_from_archive_today(url)
                        logger.info(f"Successfully extracted from archive.today")
                        return content
                    except ExtractionError as archive_error:
                        logger.warning(
                            f"archive.today fallback failed for {url}: {archive_error}"
                        )

                # Fallback 5: Try Google Cache
                if should_try_google_cache(url):
                    logger.info(f"Trying Google Cache fallback for: {url}")
                    try:
                        content = await self.archive_extractor.extract_from_google_cache(url)
                        logger.info(f"Successfully extracted from Google Cache")
                        return content
                    except ExtractionError as cache_error:
                        logger.warning(
                            f"Google Cache fallback failed for {url}: {cache_error}"
                        )

                # Fallback 6: Try Wayback Machine as last resort
                logger.info(f"Trying Wayback Machine fallback for: {url}")
                archived_html = await self.wayback.fetch_archived_content(url)

                if archived_html:
                    # Re-extract from archived HTML
                    import trafilatura

                    text = trafilatura.extract(archived_html, url=url)
                    if text:
                        content = self.article_extractor._create_content(
                            url=url,
                            raw_text=text,
                            fallback_used=True,
                        )
                        content.extraction_method = "trafilatura_wayback"
                        return content

            # Re-raise if all fallbacks failed
            raise

    async def _fact_check_content(
        self,
        content: ExtractedContent,
    ) -> FactCheckReport:
        """Fact-check the extracted content."""
        # First, extract claims using LLM
        claims = await self.summarizer.extract_claims(
            content.raw_text,
            max_claims=5,
        )

        if not claims:
            # Fallback to heuristic claim extraction
            return await self.fact_checker.check_content(
                content.raw_text,
                max_claims=5,
            )

        # Check each extracted claim
        verified_claims = []
        unverified_claims = []

        for claim in claims:
            results = await self.fact_checker.check_claim(claim)
            if results:
                verified_claims.extend(results)
            else:
                unverified_claims.append(claim)

        return FactCheckReport(
            claims_analyzed=len(claims),
            verified_claims=verified_claims,
            unverified_claims=unverified_claims,
        )


# Convenience function for quick processing
async def process_url(url: str, **kwargs) -> ProcessedResult:
    """
    Convenience function to process a single URL.

    Args:
        url: The URL to process.
        **kwargs: Additional arguments passed to NewsAgent.process()

    Returns:
        ProcessedResult with the processed content.
    """
    agent = NewsAgent()
    try:
        return await agent.process(url, **kwargs)
    finally:
        await agent.close()


async def process_urls(urls: List[str], **kwargs) -> List[ProcessedResult]:
    """
    Convenience function to process multiple URLs.

    Args:
        urls: List of URLs to process.
        **kwargs: Additional arguments passed to NewsAgent.process_batch()

    Returns:
        List of ProcessedResult objects.
    """
    agent = NewsAgent()
    try:
        return await agent.process_batch(urls, **kwargs)
    finally:
        await agent.close()


