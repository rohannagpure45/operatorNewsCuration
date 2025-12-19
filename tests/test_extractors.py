"""Tests for content extractors."""

import pytest

from src.extractors.router import URLRouter, URLType


class TestURLRouter:
    """Tests for URL type detection."""

    def test_twitter_url_detection(self):
        """Test Twitter/X URL detection."""
        twitter_urls = [
            "https://twitter.com/user/status/1234567890",
            "https://x.com/user/status/1234567890",
            "https://www.twitter.com/user/status/1234567890",
            "https://mobile.twitter.com/user/status/1234567890",
        ]
        for url in twitter_urls:
            assert URLRouter.detect_url_type(url) == URLType.TWITTER

    def test_sec_url_detection(self):
        """Test SEC filing URL detection."""
        sec_urls = [
            "https://www.sec.gov/cgi-bin/browse-edgar",
            "https://13f.info/manager/12345",
            "https://www.13f.info/fund/test",
        ]
        for url in sec_urls:
            assert URLRouter.detect_url_type(url) == URLType.SEC_FILING

    def test_blog_url_detection(self):
        """Test blog URL detection."""
        blog_urls = [
            "https://example.substack.com/p/article",
            "https://medium.com/@user/article",
            "https://example.medium.com/article",
            "https://blog.example.com/post",
            "https://example.com/blog/post",
        ]
        for url in blog_urls:
            assert URLRouter.detect_url_type(url) == URLType.BLOG

    def test_news_url_detection(self):
        """Test news article URL detection."""
        news_urls = [
            "https://www.bloomberg.com/news/article",
            "https://www.nytimes.com/2024/01/01/article",
            "https://techcrunch.com/article",
            "https://wired.com/story/test",
        ]
        for url in news_urls:
            assert URLRouter.detect_url_type(url) == URLType.NEWS_ARTICLE

    def test_url_validation(self):
        """Test URL validation."""
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://sub.example.com/path?query=1",
        ]
        for url in valid_urls:
            assert URLRouter.is_valid_url(url)

        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "",
            "javascript:alert(1)",
        ]
        for url in invalid_urls:
            assert not URLRouter.is_valid_url(url)

    def test_tweet_id_extraction(self):
        """Test tweet ID extraction."""
        url = "https://twitter.com/user/status/1234567890123456789"
        assert URLRouter.extract_tweet_id(url) == "1234567890123456789"

        url_no_id = "https://twitter.com/user"
        assert URLRouter.extract_tweet_id(url_no_id) is None

    def test_url_normalization(self):
        """Test URL normalization."""
        # Add https if missing
        assert URLRouter.normalize_url("example.com").startswith("https://")

        # Remove trailing slash
        assert not URLRouter.normalize_url("https://example.com/path/").endswith("/")

        # Keep root slash
        assert URLRouter.normalize_url("https://example.com/").endswith("/")


class TestArticleExtractor:
    """Tests for article extraction (requires network)."""

    @pytest.mark.asyncio
    async def test_can_handle(self):
        """Test URL handling check."""
        from src.extractors.article import ArticleExtractor

        extractor = ArticleExtractor()

        # Should handle news articles
        assert extractor.can_handle("https://example.com/article")
        assert extractor.can_handle("https://blog.example.com/post")

        # Should not handle Twitter
        assert not extractor.can_handle("https://twitter.com/user/status/123")

        # Should not handle SEC
        assert not extractor.can_handle("https://sec.gov/filing")


class TestTwitterExtractor:
    """Tests for Twitter extraction."""

    def test_can_handle(self):
        """Test URL handling check."""
        from src.extractors.twitter import TwitterExtractor

        extractor = TwitterExtractor()

        # Should handle Twitter URLs
        assert extractor.can_handle("https://twitter.com/user/status/123")
        assert extractor.can_handle("https://x.com/user/status/123")

        # Should not handle other URLs
        assert not extractor.can_handle("https://example.com")


class TestSECExtractor:
    """Tests for SEC filing extraction."""

    def test_can_handle(self):
        """Test URL handling check."""
        from src.extractors.sec_filings import SECExtractor

        extractor = SECExtractor()

        # Should handle SEC URLs
        assert extractor.can_handle("https://sec.gov/filing")
        assert extractor.can_handle("https://13f.info/fund/test")

        # Should not handle other URLs
        assert not extractor.can_handle("https://example.com")
