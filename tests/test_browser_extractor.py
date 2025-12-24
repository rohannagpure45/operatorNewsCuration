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


# =============================================================================
# Cloudflare Challenge Detection Tests
# =============================================================================


class TestCloudflareDetection:
    """Tests for _is_cloudflare_challenge() method."""

    @pytest.mark.asyncio
    async def test_detects_cloudflare_by_title_just_a_moment(self):
        """Test detection of Cloudflare challenge by 'Just a moment' title."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="Just a moment...")
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_cloudflare_by_title_checking_browser(self):
        """Test detection of Cloudflare challenge by 'Checking your browser' title."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="Checking your browser before accessing")
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_cloudflare_by_title_attention_required(self):
        """Test detection of Cloudflare challenge by 'Attention Required' title."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="Attention Required! | Cloudflare")
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_cloudflare_by_selector(self):
        """Test detection of Cloudflare challenge by CSS selector."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="Normal Page Title")
        
        # Return element for the Cloudflare challenge selector
        mock_element = MagicMock()
        mock_page.query_selector = AsyncMock(side_effect=[
            None,  # #cf-challenge-running
            None,  # #challenge-running
            None,  # .cf-browser-verification
            mock_element,  # #turnstile-wrapper - found!
        ])
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_normal_page(self):
        """Test that normal pages are not detected as Cloudflare challenges."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="OpenAI - AI Research")
        mock_page.query_selector = AsyncMock(return_value=None)  # No challenge elements
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_handles_title_exception_gracefully(self):
        """Test that exceptions during title check are handled gracefully."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(side_effect=Exception("Page closed"))
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_handles_selector_exception_gracefully(self):
        """Test that exceptions during selector check continue checking other selectors."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        mock_page.title = AsyncMock(return_value="Normal Title")
        
        # First selector raises, but we should continue
        mock_element = MagicMock()
        mock_page.query_selector = AsyncMock(side_effect=[
            Exception("Selector error"),  # #cf-challenge-running
            mock_element,  # #challenge-running - found!
        ])
        
        result = await extractor._is_cloudflare_challenge(mock_page)
        assert result is True


class TestCloudflareChallengeWait:
    """Tests for _wait_for_cloudflare_challenge() method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_challenge_resolves(self):
        """Test that method returns True when challenge resolves within time limit."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        
        # Simulate challenge resolving after first check
        with patch.object(extractor, '_is_cloudflare_challenge', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = [False]  # Resolved on first check
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await extractor._wait_for_cloudflare_challenge(mock_page, max_wait=10)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_challenge_does_not_resolve(self):
        """Test that method returns False when challenge doesn't resolve within limit."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        
        # Simulate challenge never resolving
        with patch.object(extractor, '_is_cloudflare_challenge', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True  # Always returns True (challenge active)
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await extractor._wait_for_cloudflare_challenge(mock_page, max_wait=4)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_respects_max_wait_timing(self):
        """Test that the method respects max_wait and doesn't exceed it (off-by-one fix)."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        sleep_calls = []
        
        async def mock_sleep(seconds):
            sleep_calls.append(seconds)
        
        # Simulate challenge never resolving
        with patch.object(extractor, '_is_cloudflare_challenge', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True  # Always active
            
            with patch('asyncio.sleep', side_effect=mock_sleep):
                await extractor._wait_for_cloudflare_challenge(mock_page, max_wait=15)
        
        # With max_wait=15 and check_interval=2, we should have 7 sleeps (14 seconds total)
        # Before fix: 8 sleeps (16 seconds) - exceeding max_wait
        # After fix: 7 sleeps (14 seconds) - within max_wait
        total_sleep = sum(sleep_calls)
        assert total_sleep <= 15, f"Total sleep {total_sleep}s exceeds max_wait of 15s"
        assert total_sleep == 14, f"Expected 14s of sleep, got {total_sleep}s"

    @pytest.mark.asyncio
    async def test_checks_at_regular_intervals(self):
        """Test that challenge is checked at regular 2-second intervals."""
        extractor = BrowserExtractor()
        
        mock_page = AsyncMock()
        check_count = 0
        
        async def count_checks(page):
            nonlocal check_count
            check_count += 1
            return check_count < 3  # Resolve after 2 checks
        
        with patch.object(extractor, '_is_cloudflare_challenge', side_effect=count_checks):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                result = await extractor._wait_for_cloudflare_challenge(mock_page, max_wait=10)
        
        assert result is True
        assert check_count == 3  # Called until it returns False
        # Each sleep should be 2 seconds
        for call in mock_sleep.call_args_list:
            assert call[0][0] == 2


class TestHTTPStatusHandling:
    """Tests for the simplified HTTP status checking logic."""

    @pytest.mark.asyncio
    async def test_raises_error_for_404(self):
        """Test that 404 errors raise ExtractionError."""
        extractor = BrowserExtractor()
        
        # Create mock response with 404
        mock_response = MagicMock()
        mock_response.status = 404
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()
        mock_context.close = AsyncMock()
        
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        
        extractor._browser = mock_browser
        extractor._playwright = MagicMock()
        
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("https://example.com/notfound")
        
        assert "HTTP error 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_error_for_500(self):
        """Test that 500 errors raise ExtractionError."""
        extractor = BrowserExtractor()
        
        mock_response = MagicMock()
        mock_response.status = 500
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()
        mock_context.close = AsyncMock()
        
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        
        extractor._browser = mock_browser
        extractor._playwright = MagicMock()
        
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("https://example.com/error")
        
        assert "HTTP error 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_403_with_cloudflare_challenge_raises_error(self):
        """Test that 403 with active Cloudflare challenge raises error."""
        extractor = BrowserExtractor()
        
        mock_response = MagicMock()
        mock_response.status = 403
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.title = AsyncMock(return_value="Just a moment...")  # Cloudflare title
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()
        mock_context.close = AsyncMock()
        
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        
        extractor._browser = mock_browser
        extractor._playwright = MagicMock()
        
        # Mock _is_cloudflare_challenge to return True initially, then raise
        with patch.object(extractor, '_is_cloudflare_challenge', new_callable=AsyncMock) as mock_cf:
            mock_cf.return_value = True
            with patch.object(extractor, '_wait_for_cloudflare_challenge', new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = False  # Challenge doesn't resolve
                
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.extract("https://openai.com/blocked")
        
        assert "Cloudflare challenge could not be bypassed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_403_without_cloudflare_challenge_continues(self):
        """Test that 403 without Cloudflare challenge allows extraction to continue."""
        extractor = BrowserExtractor()
        
        mock_response = MagicMock()
        mock_response.status = 403  # Initial 403
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Some content here that is long enough</body></html>" + "x" * 200)
        mock_page.mouse = MagicMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.close = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_init_script = AsyncMock()
        mock_context.close = AsyncMock()
        
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        
        extractor._browser = mock_browser
        extractor._playwright = MagicMock()
        
        # Mock _is_cloudflare_challenge to return False (no challenge)
        with patch.object(extractor, '_is_cloudflare_challenge', new_callable=AsyncMock) as mock_cf:
            mock_cf.return_value = False
            
            with patch('trafilatura.extract', return_value="This is extracted content that is long enough to pass validation." + "x" * 100):
                with patch('trafilatura.extract_metadata', return_value=None):
                    with patch('asyncio.sleep', new_callable=AsyncMock):
                        result = await extractor.extract("https://example.com/page")
        
        # Should succeed despite initial 403
        assert result is not None
        assert result.raw_text is not None
