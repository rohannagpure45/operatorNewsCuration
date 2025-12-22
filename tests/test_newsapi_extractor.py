"""Tests for NewsAPI extractor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.newsapi import NewsAPIExtractor, search_newsapi
from src.extractors.base import ExtractionError


# Sample NewsAPI response
SAMPLE_NEWSAPI_RESPONSE = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "bloomberg", "name": "Bloomberg"},
            "author": "Tech Reporter",
            "title": "AI Data Center Boom May Suck Resources Away From Roads",
            "description": "The rapid expansion of AI data centers is creating unprecedented demand for construction resources.",
            "url": "https://www.bloomberg.com/news/newsletters/2025-12-12/ai-data-center-boom",
            "urlToImage": "https://example.com/image.jpg",
            "publishedAt": "2025-12-12T10:00:00Z",
            "content": "The rapid expansion of AI data centers is creating unprecedented demand for construction resources, potentially diverting materials and labor from critical infrastructure projects. [+1500 chars]"
        }
    ]
}

SAMPLE_NEWSAPI_EMPTY = {
    "status": "ok",
    "totalResults": 0,
    "articles": []
}


class TestNewsAPIExtractor:
    """Tests for NewsAPIExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a NewsAPI extractor with a mock API key."""
        return NewsAPIExtractor(timeout=30, api_key="test_api_key")

    @pytest.fixture
    def extractor_no_key(self):
        """Create a NewsAPI extractor without an API key."""
        return NewsAPIExtractor(timeout=30, api_key=None)

    def test_is_configured_with_key(self, extractor):
        """Test that extractor reports configured with API key."""
        assert extractor.is_configured is True

    def test_is_configured_without_key(self, extractor_no_key):
        """Test that extractor reports not configured without API key."""
        assert extractor_no_key.is_configured is False

    def test_can_handle_any_url(self, extractor):
        """NewsAPI should be able to handle any URL."""
        assert extractor.can_handle("https://www.bloomberg.com/article")
        assert extractor.can_handle("https://example.com/page")

    def test_urls_match_same_path(self, extractor):
        """Test URL matching with same path."""
        url1 = "https://www.bloomberg.com/news/article-123"
        url2 = "https://www.bloomberg.com/news/article-123/"
        assert extractor._urls_match(url1, url2) is True

    def test_urls_match_different_path(self, extractor):
        """Test URL matching with different paths."""
        url1 = "https://www.bloomberg.com/news/article-123"
        url2 = "https://www.bloomberg.com/news/article-456"
        assert extractor._urls_match(url1, url2) is False

    @pytest.mark.asyncio
    async def test_extract_without_api_key(self, extractor_no_key):
        """Test extraction fails without API key."""
        with pytest.raises(ExtractionError) as exc_info:
            await extractor_no_key.extract("https://example.com/article")
        
        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_url_success(self, extractor):
        """Test successful search by URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_NEWSAPI_RESPONSE

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.search_by_url(
                "https://www.bloomberg.com/news/newsletters/2025-12-12/ai-data-center-boom"
            )

            assert result is not None
            assert result["title"] == "AI Data Center Boom May Suck Resources Away From Roads"

    @pytest.mark.asyncio
    async def test_search_by_url_not_found(self, extractor):
        """Test search returns None when article not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_NEWSAPI_EMPTY

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.search_by_url(
                "https://www.bloomberg.com/nonexistent"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_extract_success(self, extractor):
        """Test successful extraction from NewsAPI."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_NEWSAPI_RESPONSE

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.extract(
                "https://www.bloomberg.com/news/newsletters/2025-12-12/ai-data-center-boom"
            )

            assert result is not None
            assert "AI Data Center" in result.metadata.title
            assert result.extraction_method == "newsapi"
            assert result.fallback_used is True
            assert "data centers" in result.raw_text.lower()

    @pytest.mark.asyncio
    async def test_extract_article_not_found(self, extractor):
        """Test extraction fails when article not in NewsAPI."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_NEWSAPI_EMPTY

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract("https://www.bloomberg.com/nonexistent")

            assert "not found in NewsAPI" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_title_success(self, extractor):
        """Test successful search by title."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_NEWSAPI_RESPONSE

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.search_by_title(
                "AI Data Center Boom",
                domain="bloomberg.com"
            )

            assert result is not None
            assert "AI Data Center" in result["title"]

    def test_content_truncation_removal(self, extractor):
        """Test that [+N chars] truncation markers are removed."""
        article = {
            "title": "Test Article",
            "description": "Short description.",
            "content": "Full content here. [+1500 chars]",
            "source": {"name": "Test"},
            "publishedAt": "2025-12-12T10:00:00Z",
        }
        
        result = extractor._create_content_from_article(
            "https://example.com/article",
            article
        )
        
        assert "[+" not in result.raw_text
        assert "Full content here." in result.raw_text


class TestSearchNewsAPIConvenience:
    """Tests for the convenience function."""

    @pytest.mark.asyncio
    async def test_search_newsapi_not_configured(self):
        """Test convenience function returns None when not configured."""
        with patch('src.extractors.newsapi.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(newsapi_key=None)
            
            result = await search_newsapi("https://example.com/article")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_search_newsapi_success(self):
        """Test convenience function works when configured."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_NEWSAPI_RESPONSE

        with patch('src.extractors.newsapi.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(newsapi_key="test_key")
            
            with patch('src.extractors.newsapi.NewsAPIExtractor.get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_get_client.return_value = mock_client

                result = await search_newsapi(
                    "https://www.bloomberg.com/news/newsletters/2025-12-12/ai-data-center-boom"
                )

                assert result is not None
                assert "AI Data Center" in result.metadata.title

