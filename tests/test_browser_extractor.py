"""Tests for the BrowserExtractor class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.browser import BrowserExtractor
from src.extractors.base import ExtractionError


class TestBrowserExtractorCleanup:
    """Tests for browser cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_cleanup_disconnected_browser_before_reconnect(self):
        """Test that disconnected browser is closed before creating new one."""
        extractor = BrowserExtractor()
        
        # Create a mock browser that is disconnected
        mock_old_browser = MagicMock()
        mock_old_browser.is_connected.return_value = False
        mock_old_browser.close = AsyncMock()
        
        extractor._browser = mock_old_browser
        
        # Mock playwright and new browser - patch at the import location
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            mock_new_browser = MagicMock()
            mock_new_browser.is_connected.return_value = True
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_new_browser)
            
            # Also mock get_settings
            with patch('src.config.get_settings') as mock_settings:
                mock_settings.return_value.browserless_api_key = None
                
                await extractor._ensure_browser()
        
        # Verify old browser was closed
        mock_old_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_handles_close_error(self):
        """Test that errors during browser close are handled gracefully."""
        extractor = BrowserExtractor()
        
        # Create a mock browser that raises on close
        mock_old_browser = MagicMock()
        mock_old_browser.is_connected.return_value = False
        mock_old_browser.close = AsyncMock(side_effect=Exception("Close failed"))
        
        extractor._browser = mock_old_browser
        
        # Mock playwright and new browser
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            mock_new_browser = MagicMock()
            mock_new_browser.is_connected.return_value = True
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_new_browser)
            
            with patch('src.config.get_settings') as mock_settings:
                mock_settings.return_value.browserless_api_key = None
                
                # Should not raise despite close error
                await extractor._ensure_browser()
        
        # Verify close was attempted
        mock_old_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_cleanup_when_browser_is_none(self):
        """Test that no cleanup is attempted when browser is None."""
        extractor = BrowserExtractor()
        extractor._browser = None
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            mock_browser = MagicMock()
            mock_browser.is_connected.return_value = True
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            
            with patch('src.config.get_settings') as mock_settings:
                mock_settings.return_value.browserless_api_key = None
                
                await extractor._ensure_browser()
        
        # Should complete without error
        assert extractor._browser is not None


class TestBrowserlessConnection:
    """Tests for Browserless.io connection handling."""

    @pytest.mark.asyncio
    async def test_browserless_connection_error_is_sanitized(self):
        """Test that Browserless connection errors don't leak API key."""
        extractor = BrowserExtractor()
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            # Make connect_over_cdp raise an error with the API key
            api_key = "super_secret_key_12345"
            mock_pw_instance.chromium.connect_over_cdp = AsyncMock(
                side_effect=Exception(f"Connection failed to wss://chrome.browserless.io?token={api_key}")
            )
            
            with patch('src.config.get_settings') as mock_settings:
                mock_settings.return_value.browserless_api_key = api_key
                
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor._ensure_browser()
                
                # Verify the error message is sanitized
                error_message = str(exc_info.value)
                assert api_key not in error_message
                assert "Failed to connect to Browserless remote browser" in error_message

    @pytest.mark.asyncio
    async def test_browserless_uses_correct_endpoint(self):
        """Test that Browserless connection uses correct WebSocket endpoint."""
        extractor = BrowserExtractor()
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            mock_browser = MagicMock()
            mock_browser.is_connected.return_value = True
            mock_pw_instance.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
            
            api_key = "test_api_key"
            with patch('src.config.get_settings') as mock_settings:
                mock_settings.return_value.browserless_api_key = api_key
                
                await extractor._ensure_browser()
            
            # Verify connect_over_cdp was called with correct endpoint
            expected_endpoint = f"wss://chrome.browserless.io?token={api_key}"
            mock_pw_instance.chromium.connect_over_cdp.assert_called_once_with(expected_endpoint)
            assert extractor._using_browserless is True

    @pytest.mark.asyncio
    async def test_local_playwright_when_no_browserless_key(self):
        """Test that local Playwright is used when no Browserless key is set."""
        extractor = BrowserExtractor()
        
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            mock_pw_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            mock_browser = MagicMock()
            mock_browser.is_connected.return_value = True
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            
            with patch('src.config.get_settings') as mock_settings:
                mock_settings.return_value.browserless_api_key = None
                
                await extractor._ensure_browser()
            
            # Verify launch was called (not connect_over_cdp)
            mock_pw_instance.chromium.launch.assert_called_once()
            mock_pw_instance.chromium.connect_over_cdp.assert_not_called()
            assert extractor._using_browserless is False


class TestBrowserExtractorCanHandle:
    """Tests for URL handling capability."""

    def test_can_handle_http_url(self):
        """Test that HTTP URLs are handled."""
        extractor = BrowserExtractor()
        assert extractor.can_handle("http://example.com/article") is True

    def test_can_handle_https_url(self):
        """Test that HTTPS URLs are handled."""
        extractor = BrowserExtractor()
        assert extractor.can_handle("https://example.com/article") is True

    def test_cannot_handle_ftp_url(self):
        """Test that FTP URLs are not handled."""
        extractor = BrowserExtractor()
        assert extractor.can_handle("ftp://example.com/file") is False

    def test_cannot_handle_invalid_url(self):
        """Test that invalid URLs return False."""
        extractor = BrowserExtractor()
        assert extractor.can_handle("not-a-url") is False


# =============================================================================
# Browser Priority Tests for Cloudflare-Protected Sites
# =============================================================================


class TestBrowserPrioritySiteHints:
    """Tests for browser priority configuration in site hints."""

    def test_openai_has_prefer_browser_flag(self):
        """Test that OpenAI site hint has prefer_browser=True."""
        from src.extractors.site_hints import get_site_hint
        
        hint = get_site_hint("https://openai.com/index/frontierscience")
        assert hint is not None
        assert hint.prefer_browser is True

    def test_anthropic_has_prefer_browser_flag(self):
        """Test that Anthropic site hint has prefer_browser=True."""
        from src.extractors.site_hints import get_site_hint
        
        hint = get_site_hint("https://www.anthropic.com/news/article")
        assert hint is not None
        assert hint.prefer_browser is True

    def test_bloomberg_does_not_prefer_browser(self):
        """Test that paywalled sites without Cloudflare don't prefer browser."""
        from src.extractors.site_hints import get_site_hint
        
        hint = get_site_hint("https://www.bloomberg.com/news/article")
        assert hint is not None
        # Bloomberg has paywall, not Cloudflare - should not prefer browser
        assert hint.prefer_browser is False

    def test_should_prefer_browser_helper_function(self):
        """Test the should_prefer_browser() helper function."""
        from src.extractors.site_hints import should_prefer_browser
        
        # Cloudflare-protected sites
        assert should_prefer_browser("https://openai.com/index/test") is True
        assert should_prefer_browser("https://www.anthropic.com/news") is True
        
        # Non-Cloudflare sites
        assert should_prefer_browser("https://www.bloomberg.com/article") is False
        assert should_prefer_browser("https://example.com/article") is False


class TestAgentBrowserPriority:
    """Tests for agent fallback chain with browser priority."""

    def test_openai_should_prefer_browser(self):
        """Test that OpenAI URLs are flagged to prefer browser extraction."""
        from src.extractors.site_hints import should_prefer_browser
        
        assert should_prefer_browser("https://openai.com/index/frontierscience") is True

    def test_cloudflare_sites_have_rss_but_prefer_browser(self):
        """Test that Cloudflare sites have RSS available but prefer browser extraction."""
        from src.extractors.site_hints import should_prefer_browser, get_site_hint
        
        # For Cloudflare sites, we should prefer browser
        openai_url = "https://openai.com/index/frontierscience"
        
        hint = get_site_hint(openai_url)
        assert hint is not None
        assert hint.prefer_browser is True
        
        # The RSS feed exists but browser should be tried first
        assert hint.rss_feed is not None  # RSS is available
        assert should_prefer_browser(openai_url) is True  # But browser is preferred
