"""Tests for the BrowserExtractor class with dual backend support.

Tests cover both agent-browser CLI backend and Browserless.io API fallback.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.browser import BrowserExtractor, _is_agent_browser_available
from src.extractors.base import ExtractionError


class TestBrowserExtractorCLI:
    """Tests for the agent-browser CLI wrapper."""

    def test_run_cmd_success(self):
        """Test successful command execution."""
        extractor = BrowserExtractor()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"success": true, "data": {"title": "Test"}}',
                stderr=''
            )
            
            result = extractor._run_cmd("get", "title")
            
            assert result["success"] is True
            assert result["data"]["title"] == "Test"
            
            # Verify command structure
            call_args = mock_run.call_args[0][0]
            assert "agent-browser" in call_args
            assert "--session" in call_args
            assert "get" in call_args
            assert "title" in call_args
            assert "--json" in call_args

    def test_run_cmd_failure(self):
        """Test command failure raises ExtractionError."""
        extractor = BrowserExtractor()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout='',
                stderr='Connection failed'
            )
            
            with pytest.raises(ExtractionError) as exc_info:
                extractor._run_cmd("open", "https://example.com")
            
            assert "Connection failed" in str(exc_info.value)

    def test_run_cmd_timeout(self):
        """Test command timeout raises ExtractionError."""
        import subprocess
        extractor = BrowserExtractor(timeout=5)
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)
            
            with pytest.raises(ExtractionError) as exc_info:
                extractor._run_cmd("open", "https://example.com")
            
            assert "timed out" in str(exc_info.value)

    def test_run_cmd_not_found(self):
        """Test agent-browser not installed raises helpful error."""
        extractor = BrowserExtractor()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            with pytest.raises(ExtractionError) as exc_info:
                extractor._run_cmd("open", "https://example.com")
            
            assert "npm install -g agent-browser" in str(exc_info.value)

    def test_run_cmd_json_error_response(self):
        """Test handling of JSON error responses."""
        extractor = BrowserExtractor()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"success": false, "error": "Element not found"}',
                stderr=''
            )
            
            with pytest.raises(ExtractionError) as exc_info:
                extractor._run_cmd("click", "@e1")
            
            assert "Element not found" in str(exc_info.value)


class TestBrowserExtractorSession:
    """Tests for session management."""

    def test_unique_session_per_instance(self):
        """Test that each extractor instance gets a unique session ID."""
        extractor1 = BrowserExtractor()
        extractor2 = BrowserExtractor()
        
        session1 = extractor1._get_session_id()
        session2 = extractor2._get_session_id()
        
        assert session1 != session2
        assert session1.startswith("extract_")
        assert session2.startswith("extract_")

    def test_session_id_persistent(self):
        """Test that session ID is consistent within an instance."""
        extractor = BrowserExtractor()
        
        session1 = extractor._get_session_id()
        session2 = extractor._get_session_id()
        
        assert session1 == session2

    @pytest.mark.asyncio
    async def test_close_clears_session(self):
        """Test that close() clears the session ID."""
        extractor = BrowserExtractor()
        
        # Get session ID (creates it)
        _ = extractor._get_session_id()
        assert extractor._session_id is not None
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"success": true}',
                stderr=''
            )
            
            await extractor.close()
        
        assert extractor._session_id is None


class TestBrowserExtractorCloudflare:
    """Tests for Cloudflare challenge detection."""

    def test_detects_cloudflare_in_snapshot_by_title(self):
        """Test detection of Cloudflare by title in snapshot."""
        extractor = BrowserExtractor()
        
        snapshot_data = {
            "data": {
                "snapshot": '- heading "Just a moment..." [ref=e1]'
            }
        }
        
        result = extractor._is_cloudflare_challenge_from_snapshot(snapshot_data)
        assert result is True

    def test_detects_cloudflare_in_snapshot_by_turnstile(self):
        """Test detection of Cloudflare turnstile in snapshot."""
        extractor = BrowserExtractor()
        
        snapshot_data = {
            "data": {
                "snapshot": '- generic [ref=e1]\n  - iframe "turnstile-wrapper" [ref=e2]'
            }
        }
        
        result = extractor._is_cloudflare_challenge_from_snapshot(snapshot_data)
        assert result is True

    def test_no_cloudflare_for_normal_page(self):
        """Test that normal pages are not detected as Cloudflare."""
        extractor = BrowserExtractor()
        
        snapshot_data = {
            "data": {
                "snapshot": '- heading "Welcome to Example" [ref=e1]\n- button "Sign Up" [ref=e2]'
            }
        }
        
        result = extractor._is_cloudflare_challenge_from_snapshot(snapshot_data)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_cloudflare_challenge_async(self):
        """Test async Cloudflare detection via CLI commands."""
        extractor = BrowserExtractor()
        
        with patch.object(extractor, '_run_cmd_async', new_callable=AsyncMock) as mock_cmd:
            # First call: get title
            mock_cmd.side_effect = [
                {"data": {"title": "Just a moment..."}},
            ]
            
            result = await extractor._is_cloudflare_challenge()
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_cloudflare_resolves(self):
        """Test waiting for Cloudflare challenge to resolve."""
        extractor = BrowserExtractor()
        
        call_count = 0
        
        async def mock_is_cloudflare():
            nonlocal call_count
            call_count += 1
            return call_count < 3  # Resolves after 2 checks
        
        with patch.object(extractor, '_is_cloudflare_challenge', side_effect=mock_is_cloudflare):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await extractor._wait_for_cloudflare_challenge(max_wait=10)
        
        assert result is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_wait_for_cloudflare_timeout(self):
        """Test Cloudflare wait times out correctly."""
        extractor = BrowserExtractor()
        
        with patch.object(extractor, '_is_cloudflare_challenge', new_callable=AsyncMock) as mock_cf:
            mock_cf.return_value = True  # Never resolves
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await extractor._wait_for_cloudflare_challenge(max_wait=4)
        
        assert result is False


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


class TestBrowserExtractorExtraction:
    """Tests for the main extraction flow."""

    @pytest.mark.asyncio
    async def test_extract_success(self):
        """Test successful content extraction."""
        extractor = BrowserExtractor()
        
        html_content = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is a test article with enough content to pass validation.
                It contains multiple sentences and paragraphs to ensure the extraction
                works correctly. We need at least 100 characters of content here.</p>
            </article>
        </body>
        </html>
        """
        
        with patch.object(extractor, '_run_cmd_async', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.side_effect = [
                {"success": True},  # set viewport
                {"success": True},  # open URL
                {"success": True},  # wait networkidle
                {"data": {"title": "Test Article"}},  # get title (cloudflare check)
                {"data": {"snapshot": "- heading 'Test Article'"}},  # snapshot (cloudflare check)
                {"success": True},  # mouse move
                {"success": True},  # scroll down
                {"success": True},  # scroll up
                {"data": {"title": "Test Article"}},  # final cloudflare check - title
                {"data": {"snapshot": "- heading 'Test Article'"}},  # final cloudflare check - snapshot
                {"data": {"html": html_content}},  # get html
                {"success": True},  # close
            ]
            
            with patch('trafilatura.extract', return_value="This is a test article with enough content." + "x" * 100):
                with patch('trafilatura.extract_metadata', return_value=None):
                    with patch('asyncio.sleep', new_callable=AsyncMock):
                        result = await extractor.extract("https://example.com/article")
        
        assert result is not None
        assert result.raw_text is not None
        assert len(result.raw_text) > 100

    @pytest.mark.asyncio
    async def test_extract_cloudflare_blocked(self):
        """Test extraction fails when Cloudflare cannot be bypassed."""
        extractor = BrowserExtractor()
        
        with patch.object(extractor, '_run_cmd_async', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.side_effect = [
                {"success": True},  # set viewport
                {"success": True},  # open URL
                {"success": True},  # wait networkidle
                {"data": {"title": "Just a moment..."}},  # cloudflare detected
            ]
            
            with patch.object(extractor, '_wait_for_cloudflare_challenge', new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = False  # Challenge doesn't resolve
                
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    with pytest.raises(ExtractionError) as exc_info:
                        await extractor.extract("https://example.com/blocked")
        
        assert "Cloudflare challenge could not be bypassed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_empty_content(self):
        """Test extraction fails for empty content."""
        extractor = BrowserExtractor()
        
        with patch.object(extractor, '_run_cmd_async', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.side_effect = [
                {"success": True},  # set viewport
                {"success": True},  # open URL
                {"success": True},  # wait networkidle
                {"data": {"title": "Normal Page"}},  # not cloudflare
                {"data": {"snapshot": "- heading 'Normal'"}},  # not cloudflare
                {"success": True},  # mouse move
                {"success": True},  # scroll down
                {"success": True},  # scroll up
                {"data": {"title": "Normal Page"}},  # final check
                {"data": {"snapshot": "- heading 'Normal'"}},  # final check
                {"data": {"html": "<html></html>"}},  # empty HTML
            ]
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor.extract("https://example.com/empty")
        
        assert "Empty or minimal content" in str(exc_info.value)


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


class TestBrowserExtractorBackendDetection:
    """Tests for agent-browser availability detection and backend selection."""

    def test_agent_browser_detection_when_missing(self):
        """Test detection when agent-browser is not installed."""
        import src.extractors.browser as browser_module
        # Reset the cached value
        browser_module._agent_browser_available = None
        
        with patch('shutil.which', return_value=None):
            result = _is_agent_browser_available()
            assert result is False
        
        # Reset for other tests
        browser_module._agent_browser_available = None

    def test_agent_browser_detection_when_present(self):
        """Test detection when agent-browser is installed."""
        import src.extractors.browser as browser_module
        browser_module._agent_browser_available = None
        
        with patch('shutil.which', return_value='/usr/local/bin/agent-browser'):
            result = _is_agent_browser_available()
            assert result is True
        
        browser_module._agent_browser_available = None

    def test_extraction_method_property_with_cli(self):
        """Test extraction_method returns agent_browser when CLI available."""
        import src.extractors.browser as browser_module
        browser_module._agent_browser_available = None
        
        with patch('shutil.which', return_value='/usr/local/bin/agent-browser'):
            extractor = BrowserExtractor()
            assert extractor.extraction_method == "agent_browser"
        
        browser_module._agent_browser_available = None

    def test_extraction_method_property_without_cli(self):
        """Test extraction_method returns browserless_content when CLI unavailable."""
        import src.extractors.browser as browser_module
        browser_module._agent_browser_available = None
        
        with patch('shutil.which', return_value=None):
            extractor = BrowserExtractor()
            assert extractor.extraction_method == "browserless_content"
        
        browser_module._agent_browser_available = None


class TestBrowserExtractorCloudflareInHtml:
    """Tests for Cloudflare detection in HTML content."""

    def test_detects_cloudflare_just_a_moment(self):
        """Test detection of 'Just a moment' Cloudflare page."""
        extractor = BrowserExtractor()
        html = '<html><title>Just a moment...</title><body>Checking your browser</body></html>'
        assert extractor._is_cloudflare_in_html(html) is True

    def test_detects_cloudflare_turnstile(self):
        """Test detection of Cloudflare turnstile."""
        extractor = BrowserExtractor()
        html = '<html><body><div id="turnstile-wrapper"></div></body></html>'
        assert extractor._is_cloudflare_in_html(html) is True

    def test_detects_cloudflare_cf_chl(self):
        """Test detection of Cloudflare challenge token."""
        extractor = BrowserExtractor()
        html = '<html><body><input name="_cf_chl_opt" /></body></html>'
        assert extractor._is_cloudflare_in_html(html) is True

    def test_detects_cloudflare_verify_human(self):
        """Test detection of 'verify you are human' message."""
        extractor = BrowserExtractor()
        html = '<html><body><p>Please verify you are human to continue</p></body></html>'
        assert extractor._is_cloudflare_in_html(html) is True

    def test_no_cloudflare_for_normal_page(self):
        """Test that normal pages are not detected as Cloudflare."""
        extractor = BrowserExtractor()
        html = '''
        <html>
        <head><title>News Article - Example News</title></head>
        <body>
            <article>
                <h1>Breaking News</h1>
                <p>This is the content of a normal news article.</p>
            </article>
        </body>
        </html>
        '''
        assert extractor._is_cloudflare_in_html(html) is False


class TestBrowserExtractorBrowserlessAPI:
    """Tests for Browserless.io API integration."""

    @pytest.mark.asyncio
    async def test_fetch_browserless_content_success(self):
        """Test successful content fetch via Browserless API."""
        extractor = BrowserExtractor()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Test content</body></html>'
        
        with patch('src.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(browserless_api_key='test_key')
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
                
                result = await extractor._fetch_browserless_content('https://example.com')
                assert result == '<html><body>Test content</body></html>'

    @pytest.mark.asyncio
    async def test_fetch_browserless_content_no_api_key(self):
        """Test error when Browserless API key not configured."""
        extractor = BrowserExtractor()
        
        with patch('src.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(browserless_api_key=None)
            
            with pytest.raises(ExtractionError) as exc_info:
                await extractor._fetch_browserless_content('https://example.com')
            
            assert 'API key not configured' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_via_browserless_with_cloudflare_fallback(self):
        """Test extraction falls back to /unblock when Cloudflare detected."""
        extractor = BrowserExtractor()
        
        cloudflare_html = '<html><title>Just a moment...</title></html>'
        normal_html = '''
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is a test article with enough content to pass validation.
                It contains multiple sentences to ensure extraction works correctly.
                We need at least 100 characters here for the test.</p>
            </article>
        </body>
        </html>
        '''
        
        with patch.object(extractor, '_fetch_browserless_content', new_callable=AsyncMock) as mock_content:
            mock_content.return_value = cloudflare_html
            
            with patch.object(extractor, '_fetch_browserless_unblock', new_callable=AsyncMock) as mock_unblock:
                mock_unblock.return_value = normal_html
                
                with patch('trafilatura.extract', return_value='Test content ' * 20):
                    with patch('trafilatura.extract_metadata', return_value=None):
                        result = await extractor._extract_via_browserless('https://example.com')
                
                # Verify /unblock was called after Cloudflare detected
                mock_unblock.assert_called_once_with('https://example.com')
                assert result is not None

    @pytest.mark.asyncio
    async def test_extract_routes_to_browserless_when_cli_unavailable(self):
        """Test that extract() uses Browserless when CLI is not available."""
        import src.extractors.browser as browser_module
        browser_module._agent_browser_available = None
        
        extractor = BrowserExtractor()
        
        with patch('shutil.which', return_value=None):
            with patch.object(extractor, '_extract_via_browserless', new_callable=AsyncMock) as mock_browserless:
                mock_browserless.return_value = MagicMock()
                
                await extractor.extract('https://example.com')
                
                mock_browserless.assert_called_once_with('https://example.com')
        
        browser_module._agent_browser_available = None

    @pytest.mark.asyncio
    async def test_extract_routes_to_agent_browser_when_cli_available(self):
        """Test that extract() uses agent-browser CLI when available."""
        import src.extractors.browser as browser_module
        browser_module._agent_browser_available = None
        
        extractor = BrowserExtractor()
        
        with patch('shutil.which', return_value='/usr/local/bin/agent-browser'):
            with patch.object(extractor, '_extract_via_agent_browser', new_callable=AsyncMock) as mock_cli:
                mock_cli.return_value = MagicMock()
                
                await extractor.extract('https://example.com')
                
                mock_cli.assert_called_once_with('https://example.com')
        
        browser_module._agent_browser_available = None

    @pytest.mark.asyncio
    async def test_fetch_browserless_unblock_invalid_json(self):
        """Test that invalid JSON response raises ExtractionError with helpful message."""
        import json
        extractor = BrowserExtractor()
        
        # Mock response that returns HTML instead of JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Error: Internal Server Error</body></html>'
        mock_response.json.side_effect = json.JSONDecodeError("No JSON object could be decoded", "<html>", 0)
        
        with patch('src.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(browserless_api_key='test_key')
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
                
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor._fetch_browserless_unblock('https://example.com')
                
                # Verify error message is helpful
                error_msg = str(exc_info.value)
                assert 'invalid JSON' in error_msg or 'JSON' in error_msg
                assert 'example.com' in error_msg

    @pytest.mark.asyncio
    async def test_fetch_browserless_unblock_malformed_json(self):
        """Test that malformed JSON response raises ExtractionError."""
        import json
        extractor = BrowserExtractor()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"incomplete": '
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", '{"incomplete": ', 14)
        
        with patch('src.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(browserless_api_key='test_key')
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
                
                with pytest.raises(ExtractionError) as exc_info:
                    await extractor._fetch_browserless_unblock('https://example.com')
                
                assert 'JSON' in str(exc_info.value)
