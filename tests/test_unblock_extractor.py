"""Tests for the UnblockExtractor class using Browserless /unblock API."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.extractors.base import ExtractionError


# =============================================================================
# PHASE 1: CRAWL - Basic /unblock API Client Tests
# =============================================================================


class TestUnblockExtractorBasicAPI:
    """Tests for basic /unblock API functionality."""

    @pytest.mark.asyncio
    async def test_fetch_content_calls_correct_endpoint(self):
        """Test that fetch_content calls the correct Browserless /unblock endpoint."""
        from src.extractors.unblock import UnblockExtractor

        api_key = "test_api_key"
        test_url = "https://example.com/article"

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = api_key
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            # Mock the httpx client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": "<html><body>Test content</body></html>",
                "cookies": [],
                "screenshot": None,
                "browserWSEndpoint": None,
            }

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                html = await extractor.fetch_content(test_url)

                # Verify the correct endpoint was called
                call_args = mock_client.post.call_args
                endpoint_url = call_args[0][0]
                assert "production-sfo.browserless.io/unblock" in endpoint_url
                assert f"token={api_key}" in endpoint_url

                # Verify the payload
                payload = call_args[1]["json"]
                assert payload["url"] == test_url
                assert payload["content"] is True

    @pytest.mark.asyncio
    async def test_fetch_content_returns_html(self):
        """Test that fetch_content returns the HTML content from the API response."""
        from src.extractors.unblock import UnblockExtractor

        expected_html = "<html><body><h1>Article Title</h1><p>Article content here.</p></body></html>"

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": expected_html,
                "cookies": [],
                "screenshot": None,
                "browserWSEndpoint": None,
            }

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                html = await extractor.fetch_content("https://example.com")

                assert html == expected_html

    @pytest.mark.asyncio
    async def test_fetch_content_handles_4xx_error(self):
        """Test that 4xx errors raise ExtractionError."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                assert "400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_content_handles_5xx_error(self):
        """Test that 5xx errors raise ExtractionError."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_content_handles_timeout(self):
        """Test that timeouts are handled gracefully."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_api_key_not_leaked_in_errors(self):
        """Test that API key is never exposed in error messages."""
        from src.extractors.unblock import UnblockExtractor

        api_key = "super_secret_browserless_key_12345"

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = api_key
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            # Simulate an error that might include the API key
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPError(
                    f"Connection failed to https://production-sfo.browserless.io/unblock?token={api_key}"
                )
            )

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                error_message = str(exc_info.value)
                assert api_key not in error_message

    @pytest.mark.asyncio
    async def test_fetch_content_handles_empty_response(self):
        """Test that empty content in response raises ExtractionError."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": "",
                "cookies": [],
                "screenshot": None,
                "browserWSEndpoint": None,
            }

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_content_handles_null_content(self):
        """Test that null content in response raises ExtractionError."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": None,
                "cookies": [],
                "screenshot": None,
                "browserWSEndpoint": None,
            }

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                assert "empty" in str(exc_info.value).lower() or "content" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_raises_error_when_no_api_key(self):
        """Test that ExtractionError is raised when no API key is configured."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = None
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.fetch_content("https://example.com")

            assert "api key" in str(exc_info.value).lower()


class TestUnblockExtractorCanHandle:
    """Tests for URL handling capability."""

    def test_can_handle_http_url(self):
        """Test that HTTP URLs are handled."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()
            assert extractor.can_handle("http://example.com/article") is True

    def test_can_handle_https_url(self):
        """Test that HTTPS URLs are handled."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()
            assert extractor.can_handle("https://example.com/article") is True

    def test_cannot_handle_ftp_url(self):
        """Test that FTP URLs are not handled."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()
            assert extractor.can_handle("ftp://example.com/file") is False

    def test_cannot_handle_invalid_url(self):
        """Test that invalid URLs return False."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()
            assert extractor.can_handle("not-a-url") is False


# =============================================================================
# PHASE 2: WALK - Pipeline Integration Tests
# =============================================================================


class TestUnblockExtractorExtract:
    """Tests for the extract() method with trafilatura integration."""

    @pytest.mark.asyncio
    async def test_extract_parses_html_with_trafilatura(self):
        """Test that extract() parses HTML content using trafilatura."""
        from src.extractors.unblock import UnblockExtractor

        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Article Title</title></head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is the first paragraph of the article content.</p>
                <p>This is the second paragraph with more meaningful text to ensure
                trafilatura extracts it properly. We need enough content here.</p>
                <p>The article continues with additional paragraphs to meet the
                minimum content threshold for extraction.</p>
            </article>
        </body>
        </html>
        """

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": html_content}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                result = await extractor.extract("https://example.com/article")

                # Verify we got an ExtractedContent object
                from src.models.schemas import ExtractedContent
                assert isinstance(result, ExtractedContent)

                # Verify the content was extracted (not raw HTML)
                assert "<html>" not in result.raw_text
                assert "paragraph" in result.raw_text.lower() or "content" in result.raw_text.lower()

    @pytest.mark.asyncio
    async def test_extract_extracts_metadata(self):
        """Test that extract() extracts metadata from HTML."""
        from src.extractors.unblock import UnblockExtractor

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Breaking News: Important Event</title>
            <meta name="author" content="John Doe">
            <meta property="article:published_time" content="2024-01-15T10:30:00Z">
        </head>
        <body>
            <article>
                <h1>Breaking News: Important Event</h1>
                <p>This is a comprehensive news article about an important event
                that happened recently. The article provides detailed coverage
                of all the relevant facts and context.</p>
                <p>Additional paragraphs provide more information about the topic,
                including quotes from experts and background information.</p>
            </article>
        </body>
        </html>
        """

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": html_content}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                result = await extractor.extract("https://example.com/article")

                # Verify metadata was extracted
                assert result.metadata is not None
                # Title should be extracted
                assert result.metadata.title is not None or "Breaking News" in result.raw_text

    @pytest.mark.asyncio
    async def test_extract_sets_extraction_method(self):
        """Test that extract() sets the correct extraction method."""
        from src.extractors.unblock import UnblockExtractor

        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>Sufficient content for extraction to succeed with trafilatura.
                We need multiple paragraphs of meaningful text here.</p>
                <p>More content to ensure the extraction threshold is met.</p>
            </article>
        </body>
        </html>
        """

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": html_content}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                result = await extractor.extract("https://example.com/article")

                assert result.extraction_method == "browserless_unblock"

    @pytest.mark.asyncio
    async def test_extract_sets_fallback_used_flag(self):
        """Test that extract() sets fallback_used to True."""
        from src.extractors.unblock import UnblockExtractor

        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>Content that is sufficient for extraction.</p>
                <p>Additional content paragraphs for the test.</p>
            </article>
        </body>
        </html>
        """

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": html_content}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                result = await extractor.extract("https://example.com/article")

                assert result.fallback_used is True


class TestUnblockExtractorResidentialProxy:
    """Tests for residential proxy configuration."""

    @pytest.mark.asyncio
    async def test_residential_proxy_added_when_configured(self):
        """Test that residential proxy parameter is added when configured."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = True

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": "<html>content</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                await extractor.fetch_content("https://example.com")

                call_args = mock_client.post.call_args
                endpoint_url = call_args[0][0]
                # Check if proxy=residential is in the URL
                assert "proxy=residential" in endpoint_url

    @pytest.mark.asyncio
    async def test_no_proxy_when_not_configured(self):
        """Test that no proxy parameter is added when not configured."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": "<html>content</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                await extractor.fetch_content("https://example.com")

                call_args = mock_client.post.call_args
                endpoint_url = call_args[0][0]
                # Check that proxy parameter is NOT in the URL
                assert "proxy=" not in endpoint_url


class TestUnblockExtractorTimeout:
    """Tests for timeout configuration."""

    @pytest.mark.asyncio
    async def test_respects_extraction_timeout_from_settings(self):
        """Test that the extractor uses timeout from settings."""
        from src.extractors.unblock import UnblockExtractor

        custom_timeout = 45

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = custom_timeout

            extractor = UnblockExtractor()

            assert extractor.timeout == custom_timeout

    @pytest.mark.asyncio
    async def test_timeout_passed_to_request(self):
        """Test that timeout is passed to the HTTP request."""
        from src.extractors.unblock import UnblockExtractor

        custom_timeout = 45

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = custom_timeout
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": "<html>test</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                await extractor.fetch_content("https://example.com")

                call_args = mock_client.post.call_args
                assert call_args[1]["timeout"] == custom_timeout

    def test_custom_timeout_overrides_settings(self):
        """Test that custom timeout in constructor overrides settings."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor(timeout=60)

            assert extractor.timeout == 60


# =============================================================================
# PHASE 3: RUN - Production Hardening Tests
# =============================================================================


class TestUnblockExtractorRetryLogic:
    """Tests for retry logic on transient failures."""

    @pytest.mark.asyncio
    async def test_retries_on_5xx_error(self):
        """Test that 5xx errors trigger retry."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            # First call fails with 503, second succeeds
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 503
            mock_response_fail.text = "Service Unavailable"

            mock_response_success = MagicMock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {"content": "<html>test</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=[mock_response_fail, mock_response_success]
            )

            with patch.object(extractor, "get_client", return_value=mock_client):
                html = await extractor.fetch_content_with_retry("https://example.com")

                # Should have retried and succeeded
                assert html == "<html>test</html>"
                assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        """Test that timeouts trigger retry."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            # First call times out, second succeeds
            mock_response_success = MagicMock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {"content": "<html>test</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=[
                    httpx.TimeoutException("timeout"),
                    mock_response_success,
                ]
            )

            with patch.object(extractor, "get_client", return_value=mock_client):
                html = await extractor.fetch_content_with_retry("https://example.com")

                assert html == "<html>test</html>"
                assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self):
        """Test that extraction fails after max retries."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            # All calls fail
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 503
            mock_response_fail.text = "Service Unavailable"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response_fail)

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError):
                    await extractor.fetch_content_with_retry(
                        "https://example.com", max_retries=3
                    )

                # Should have tried max_retries + 1 times (initial + retries)
                assert mock_client.post.call_count == 4

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_error(self):
        """Test that 4xx errors do not trigger retry."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError):
                    await extractor.fetch_content_with_retry("https://example.com")

                # Should NOT retry on 4xx errors
                assert mock_client.post.call_count == 1


class TestUnblockExtractorWaitForOptions:
    """Tests for waitFor configuration options."""

    @pytest.mark.asyncio
    async def test_wait_for_timeout_in_payload(self):
        """Test that waitForTimeout is included in API payload."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": "<html>test</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                await extractor.fetch_content(
                    "https://example.com", wait_for_timeout=2000
                )

                call_args = mock_client.post.call_args
                payload = call_args[1]["json"]
                assert payload.get("waitForTimeout") == 2000

    @pytest.mark.asyncio
    async def test_wait_for_selector_in_payload(self):
        """Test that waitForSelector is included in API payload."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30
            mock_settings.return_value.browserless_use_residential_proxy = False

            extractor = UnblockExtractor()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"content": "<html>test</html>"}

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(extractor, "get_client", return_value=mock_client):
                await extractor.fetch_content(
                    "https://example.com", wait_for_selector="article"
                )

                call_args = mock_client.post.call_args
                payload = call_args[1]["json"]
                assert payload.get("waitForSelector") == {"selector": "article"}


class TestUnblockExtractorGracefulDegradation:
    """Tests for graceful degradation when API is unavailable."""

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        """Test that extractor returns gracefully when disabled."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = None
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            # Should raise ExtractionError, not crash
            with pytest.raises(ExtractionError) as exc_info:
                await extractor.fetch_content("https://example.com")

            assert "api key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_handles_connection_refused(self):
        """Test graceful handling of connection refused errors."""
        from src.extractors.unblock import UnblockExtractor

        with patch("src.extractors.unblock.get_settings") as mock_settings:
            mock_settings.return_value.browserless_api_key = "test_key"
            mock_settings.return_value.extraction_timeout = 30

            extractor = UnblockExtractor()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            with patch.object(extractor, "get_client", return_value=mock_client):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.fetch_content("https://example.com")

                # Error should be wrapped in ExtractionError
                assert "Connection refused" in str(exc_info.value) or "request failed" in str(exc_info.value).lower()


class TestUnblockExtractorIntegration:
    """Integration tests with real API (skipped in CI)."""

    @pytest.mark.skip(reason="Requires real Browserless API key")
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """Test against real Browserless API."""
        import os
        from src.extractors.unblock import UnblockExtractor

        # Only run if API key is set
        api_key = os.environ.get("BROWSERLESS_API_KEY")
        if not api_key:
            pytest.skip("BROWSERLESS_API_KEY not set")

        extractor = UnblockExtractor()
        try:
            result = await extractor.extract("https://example.com")
            assert result is not None
            assert len(result.raw_text) > 0
        finally:
            await extractor.close()
