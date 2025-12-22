"""Tests for archive services extractor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.archives import ArchiveExtractor, extract_from_archives
from src.extractors.base import ExtractionError


# Sample archived HTML content for testing
SAMPLE_ARCHIVED_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bloomberg Article - AI Data Centers</title>
    <meta name="author" content="Tech Reporter">
    <meta name="date" content="2025-12-12">
</head>
<body>
    <article>
        <h1>AI Data Center Boom May Suck Resources Away From Roads</h1>
        <p class="byline">By Tech Reporter</p>
        <div class="article-body">
            <p>The rapid expansion of AI data centers is creating unprecedented demand 
            for construction resources, potentially diverting materials and labor from 
            critical infrastructure projects like roads and bridges.</p>
            <p>Industry experts warn that this competition for resources could delay 
            essential public works projects across the country.</p>
            <p>The trend is particularly pronounced in regions with significant tech 
            industry presence, where data center construction has accelerated sharply.</p>
        </div>
    </article>
</body>
</html>
"""

SAMPLE_GOOGLE_CACHE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>WSJ Article - Meta AI</title>
</head>
<body>
    <div style="background:#fff; border:1px solid #ccc;">
        This is Google's cache of https://www.wsj.com/article.
    </div>
    <article>
        <h1>Meta Developing New AI Model Code-Named Mango</h1>
        <p>Meta is working on a new AI image and video generation model.</p>
        <p>The project, internally known as Mango, aims to compete with OpenAI.</p>
        <p>Sources familiar with the matter say development is progressing rapidly.</p>
    </article>
</body>
</html>
"""

ARCHIVE_TODAY_NOT_FOUND = """
<!DOCTYPE html>
<html>
<head><title>archive.today</title></head>
<body>
    <form action="https://archive.today/submit/">
        <input type="text" name="url" />
        <input type="submit" value="save" />
    </form>
    <p>No results for this URL.</p>
</body>
</html>
"""


class TestArchiveExtractor:
    """Tests for ArchiveExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create an archive extractor instance."""
        return ArchiveExtractor(timeout=30)

    def test_can_handle_http_urls(self, extractor):
        """Archive extractor should handle HTTP(S) URLs."""
        assert extractor.can_handle("https://www.bloomberg.com/article")
        assert extractor.can_handle("http://example.com/page")
        assert not extractor.can_handle("ftp://files.example.com")

    def test_is_valid_archive_page_with_content(self, extractor):
        """Test detection of valid archived pages."""
        valid_html = '<html><div id="CONTENT">Article content here</div></html>'
        assert extractor._is_valid_archive_page(valid_html, "archive.today")

    def test_is_valid_archive_page_no_results(self, extractor):
        """Test detection of 'no results' pages."""
        assert not extractor._is_valid_archive_page(
            ARCHIVE_TODAY_NOT_FOUND, "archive.today"
        )

    def test_clean_archive_today_html(self, extractor):
        """Test cleaning of archive.today specific elements."""
        html = '''
        <div id="HEADER">Archive toolbar</div>
        <script>tracking code</script>
        <article>Actual content</article>
        '''
        cleaned = extractor._clean_archive_today_html(html)
        assert 'id="HEADER"' not in cleaned
        assert "<script>" not in cleaned
        assert "<article>" in cleaned

    def test_clean_google_cache_html(self, extractor):
        """Test cleaning of Google Cache specific elements."""
        cleaned = extractor._clean_google_cache_html(SAMPLE_GOOGLE_CACHE_HTML)
        # The article content should remain
        assert "Meta Developing" in cleaned

    @pytest.mark.asyncio
    async def test_extract_from_archive_today_success(self, extractor):
        """Test successful extraction from archive.today."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_ARCHIVED_HTML
        mock_response.url = "https://archive.today/abc123"

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # Mock _is_valid_archive_page to return True
            with patch.object(extractor, '_is_valid_archive_page', return_value=True):
                result = await extractor.extract_from_archive_today(
                    "https://www.bloomberg.com/article"
                )

                assert result is not None
                assert "data center" in result.raw_text.lower()
                assert result.extraction_method == "archive_today"
                assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_extract_from_archive_today_not_found(self, extractor):
        """Test archive.today returns not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ARCHIVE_TODAY_NOT_FOUND
        mock_response.url = "https://archive.today/search"

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract_from_archive_today(
                    "https://www.bloomberg.com/nonexistent"
                )

            assert "No archive.today snapshot found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_from_google_cache_success(self, extractor):
        """Test successful extraction from Google Cache."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_GOOGLE_CACHE_HTML
        mock_response.url = "https://webcache.googleusercontent.com/search?q=cache:xyz"

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.extract_from_google_cache(
                "https://www.wsj.com/article"
            )

            assert result is not None
            assert "Meta" in result.raw_text
            assert "Mango" in result.raw_text
            assert result.extraction_method == "google_cache"

    @pytest.mark.asyncio
    async def test_extract_from_google_cache_not_found(self, extractor):
        """Test Google Cache returns 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract_from_google_cache(
                    "https://www.wsj.com/nonexistent"
                )

            assert "No Google Cache found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_tries_multiple_services(self, extractor):
        """Test that extract() tries archive.today then Google Cache."""
        # Mock archive.today to fail
        archive_response = MagicMock()
        archive_response.status_code = 200
        archive_response.text = ARCHIVE_TODAY_NOT_FOUND
        archive_response.url = "https://archive.today"

        # Mock Google Cache to succeed
        cache_response = MagicMock()
        cache_response.status_code = 200
        cache_response.text = SAMPLE_GOOGLE_CACHE_HTML
        cache_response.url = "https://webcache.googleusercontent.com/search?q=cache:xyz"

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            url = args[0] if args else kwargs.get('url', '')
            if "archive" in str(url):
                return archive_response
            return cache_response

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_get_client.return_value = mock_client

            result = await extractor.extract(
                "https://www.wsj.com/article"
            )

            # Should have tried archive.today domains first (up to 4), then Google Cache
            # At minimum: 1 archive.today + 1 Google Cache = 2 calls
            assert call_count >= 2
            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_all_services_fail(self, extractor):
        """Test error when all archive services fail."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract("https://www.example.com/article")

            assert "No archived version found" in str(exc_info.value)


class TestExtractFromArchivesConvenience:
    """Tests for the convenience function."""

    @pytest.mark.asyncio
    async def test_extract_from_archives_function(self):
        """Test the convenience function works."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_ARCHIVED_HTML
        mock_response.url = "https://archive.today/abc123"

        with patch('src.extractors.archives.ArchiveExtractor.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch('src.extractors.archives.ArchiveExtractor._is_valid_archive_page', return_value=True):
                result = await extract_from_archives(
                    url="https://www.bloomberg.com/article",
                )

                assert result is not None
                assert result.fallback_used is True


class TestArchiveURLPatterns:
    """Tests for archive URL construction."""

    def test_archive_today_domains(self):
        """Verify archive.today domains are configured."""
        extractor = ArchiveExtractor()
        assert "archive.today" in extractor.ARCHIVE_TODAY_DOMAINS
        assert "archive.is" in extractor.ARCHIVE_TODAY_DOMAINS
        assert len(extractor.ARCHIVE_TODAY_DOMAINS) >= 3

