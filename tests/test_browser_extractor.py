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
