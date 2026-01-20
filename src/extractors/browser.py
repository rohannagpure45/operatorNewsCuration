"""Browser-based content extractor with automatic backend selection.

Uses agent-browser CLI when available (local/Docker) or falls back to
Browserless.io API (Streamlit Cloud) for sites that block httpx.
"""

import asyncio
import json
import logging
import random
import shutil
import subprocess
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx

import trafilatura

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType

logger = logging.getLogger(__name__)

# Cloudflare challenge detection patterns (for snapshot analysis)
CLOUDFLARE_CHALLENGE_TITLES = [
    "just a moment",
    "attention required",
    "checking your browser",
    "please wait",
    "ddos protection",
    "cloudflare",
]

# Common viewport sizes for randomization
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]

# Browserless.io API endpoint for /content API
BROWSERLESS_CONTENT_URL = "https://chrome.browserless.io/content"

# Cache for agent-browser availability check
_agent_browser_available: Optional[bool] = None


def _is_agent_browser_available() -> bool:
    """Check if agent-browser CLI is installed and accessible.
    
    Returns:
        True if agent-browser CLI is found in PATH, False otherwise.
    """
    global _agent_browser_available
    if _agent_browser_available is None:
        _agent_browser_available = shutil.which("agent-browser") is not None
        if _agent_browser_available:
            logger.debug("agent-browser CLI found, using CLI backend")
        else:
            logger.debug("agent-browser CLI not found, will use Browserless API")
    return _agent_browser_available

class BrowserExtractor(BaseExtractor):
    """
    Extract content from websites using browser automation.
    
    This extractor automatically selects the best available backend:
    - agent-browser CLI: Used when installed (local/Docker environments)
    - Browserless.io API: Used as fallback (Streamlit Cloud)
    
    Designed as a fallback for sites that block httpx requests with 403 errors
    or require JavaScript rendering.
    """

    url_type = URLType.NEWS_ARTICLE

    @property
    def extraction_method(self) -> str:
        """Return the extraction method based on available backend."""
        if _is_agent_browser_available():
            return "agent_browser"
        return "browserless_content"


    def __init__(self, timeout: int = 60, headless: bool = True):
        """
        Initialize the browser extractor.
        
        Args:
            timeout: Maximum time to wait for operations in seconds.
            headless: Whether to run the browser in headless mode (always True for agent-browser).
        """
        super().__init__(timeout)
        self.headless = headless
        # Use unique session ID for isolation between extractions
        self._session_id: Optional[str] = None

    def _get_session_id(self) -> str:
        """Get or create a unique session ID for this extraction."""
        if self._session_id is None:
            self._session_id = f"extract_{uuid.uuid4().hex[:8]}"
        return self._session_id

    def _run_cmd(self, *args, timeout: Optional[int] = None) -> dict:
        """
        Run an agent-browser command and return the JSON result.
        
        Args:
            *args: Command arguments to pass to agent-browser.
            timeout: Optional timeout override in seconds.
            
        Returns:
            Parsed JSON response from agent-browser.
            
        Raises:
            ExtractionError: If the command fails or returns an error.
        """
        cmd = ["agent-browser", "--session", self._get_session_id(), *args]
        
        # Add --json flag for machine-readable output if not already present
        if "--json" not in args:
            cmd.append("--json")
        
        effective_timeout = timeout or self.timeout
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or f"Command failed with code {result.returncode}"
                raise ExtractionError(f"agent-browser error: {error_msg}")
            
            # Parse JSON response
            try:
                response = json.loads(result.stdout)
                if not response.get("success", True):
                    error = response.get("error", "Unknown error")
                    raise ExtractionError(f"agent-browser error: {error}")
                return response
            except json.JSONDecodeError:
                # Some commands may return non-JSON output
                return {"success": True, "data": result.stdout.strip()}
                
        except subprocess.TimeoutExpired:
            raise ExtractionError(f"agent-browser command timed out after {effective_timeout}s")
        except FileNotFoundError:
            raise ExtractionError(
                "agent-browser CLI not found. Install with: npm install -g agent-browser"
            )

    async def _run_cmd_async(self, *args, timeout: Optional[int] = None) -> dict:
        """
        Run an agent-browser command asynchronously.
        
        Wraps _run_cmd in asyncio.to_thread for non-blocking execution.
        """
        return await asyncio.to_thread(self._run_cmd, *args, timeout=timeout)

    async def close(self) -> None:
        """Close the browser session."""
        if self._session_id:
            try:
                await self._run_cmd_async("close")
            except ExtractionError:
                pass  # Ignore errors closing already-closed session
            self._session_id = None

    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle the URL.
        
        BrowserExtractor can handle any HTTP(S) URL.
        """
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    def _is_cloudflare_challenge_from_snapshot(self, snapshot_data: dict) -> bool:
        """
        Check if the snapshot indicates a Cloudflare challenge page.
        
        Args:
            snapshot_data: Parsed JSON response from agent-browser snapshot.
            
        Returns:
            True if Cloudflare challenge is detected.
        """
        try:
            snapshot_text = snapshot_data.get("data", {}).get("snapshot", "")
            snapshot_lower = snapshot_text.lower()
            
            # Check for Cloudflare challenge indicators in the accessibility tree
            for pattern in CLOUDFLARE_CHALLENGE_TITLES:
                if pattern in snapshot_lower:
                    return True
            
            # Check for specific Cloudflare UI elements
            cloudflare_indicators = [
                "turnstile",
                "challenge-running",
                "cf-browser-verification",
                "verify you are human",
            ]
            for indicator in cloudflare_indicators:
                if indicator in snapshot_lower:
                    return True
            
            return False
        except Exception:
            return False

    async def _is_cloudflare_challenge(self, page=None) -> bool:
        """
        Check if the current page is showing a Cloudflare challenge.
        
        Uses agent-browser snapshot to analyze the page.
        """
        try:
            # Get page title
            title_result = await self._run_cmd_async("get", "title")
            title = title_result.get("data", {}).get("title", "")
            
            if title and any(pattern in title.lower() for pattern in CLOUDFLARE_CHALLENGE_TITLES):
                return True
            
            # Get interactive snapshot for more detailed analysis
            snapshot_result = await self._run_cmd_async("snapshot", "-i", "-c")
            return self._is_cloudflare_challenge_from_snapshot(snapshot_result)
            
        except Exception:
            return False

    async def _wait_for_cloudflare_challenge(self, page=None, max_wait: int = 15) -> bool:
        """
        Wait for Cloudflare challenge to resolve.
        
        Args:
            page: Unused, kept for API compatibility.
            max_wait: Maximum seconds to wait for challenge resolution.
            
        Returns:
            True if challenge resolved, False if still blocked.
        """
        logger.info("Cloudflare challenge detected, waiting for resolution...")
        
        elapsed = 0
        check_interval = 2  # Check every 2 seconds
        
        while elapsed + check_interval <= max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if not await self._is_cloudflare_challenge():
                logger.info(f"Cloudflare challenge resolved after {elapsed}s")
                return True
            
            logger.debug(f"Still waiting for Cloudflare challenge... ({elapsed}s/{max_wait}s)")
        
        logger.warning(f"Cloudflare challenge did not resolve within {max_wait}s")
        return False

    def _is_cloudflare_in_html(self, html: str) -> bool:
        """Detect Cloudflare challenge in HTML content.
        
        Used by Browserless backend since we can't use snapshot analysis.
        
        Args:
            html: Raw HTML content to check.
            
        Returns:
            True if Cloudflare challenge indicators found.
        """
        html_lower = html.lower()
        patterns = [
            "just a moment",
            "checking your browser",
            "cf-browser-verification",
            "turnstile",
            "_cf_chl",
            "challenge-running",
            "verify you are human",
        ]
        return any(p in html_lower for p in patterns)

    async def _fetch_browserless_content(self, url: str) -> str:
        """Fetch HTML content using Browserless.io /content API.
        
        Args:
            url: URL to fetch.
            
        Returns:
            Raw HTML content.
            
        Raises:
            ExtractionError: If API call fails.
        """
        from src.config import get_settings
        settings = get_settings()
        
        if not settings.browserless_api_key:
            raise ExtractionError(
                "Browserless API key not configured. "
                "Set BROWSERLESS_API_KEY environment variable."
            )
        
        # Sanitize API key for error messages
        api_key = settings.browserless_api_key
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BROWSERLESS_CONTENT_URL}?token={api_key}",
                    json={
                        "url": url,
                        "waitForTimeout": random.randint(3000, 5000),
                        "gotoOptions": {"waitUntil": "networkidle0"},
                    },
                    timeout=self.timeout,
                )
                
                if response.status_code >= 400:
                    raise ExtractionError(
                        f"Browserless API error: status {response.status_code}"
                    )
                
                return response.text
                
        except httpx.TimeoutException:
            raise ExtractionError(
                f"Browserless API request timed out for: {url}"
            ) from None
        except httpx.HTTPError as e:
            # Sanitize error to avoid leaking API key
            error_str = str(e)
            if api_key and api_key in error_str:
                error_str = error_str.replace(api_key, "[REDACTED]")
            raise ExtractionError(
                f"Browserless API request failed: {error_str}"
            ) from None

    async def _fetch_browserless_unblock(self, url: str) -> str:
        """Fetch HTML content using Browserless.io /unblock API.
        
        Used as fallback when /content returns Cloudflare challenge.
        
        Args:
            url: URL to fetch.
            
        Returns:
            Raw HTML content.
            
        Raises:
            ExtractionError: If API call fails.
        """
        from src.config import get_settings
        settings = get_settings()
        
        if not settings.browserless_api_key:
            raise ExtractionError("Browserless API key not configured")
        
        api_key = settings.browserless_api_key
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://production-sfo.browserless.io/unblock?token={api_key}",
                    json={
                        "url": url,
                        "content": True,
                    },
                    timeout=self.timeout,
                )
                
                if response.status_code >= 400:
                    raise ExtractionError(
                        f"Browserless /unblock API error: status {response.status_code}"
                    )
                
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    # Response was not valid JSON
                    preview = response.text[:200] if response.text else "(empty)"
                    raise ExtractionError(
                        f"Browserless /unblock returned invalid JSON for {url}: {e}. "
                        f"Response preview: {preview}"
                    ) from None
                
                content = data.get("content")
                
                if not content:
                    raise ExtractionError(
                        f"Browserless /unblock returned empty content for: {url}"
                    )
                
                return content
                
        except httpx.TimeoutException:
            raise ExtractionError(
                f"Browserless /unblock request timed out for: {url}"
            ) from None
        except httpx.HTTPError as e:
            error_str = str(e)
            if api_key and api_key in error_str:
                error_str = error_str.replace(api_key, "[REDACTED]")
            raise ExtractionError(
                f"Browserless /unblock request failed: {error_str}"
            ) from None

    async def _extract_via_browserless(self, url: str) -> ExtractedContent:
        """Extract content using Browserless.io API.
        
        Tries /content API first, falls back to /unblock if Cloudflare detected.
        
        Args:
            url: URL to extract.
            
        Returns:
            ExtractedContent with parsed text and metadata.
            
        Raises:
            ExtractionError: If extraction fails.
        """
        logger.info(f"Using Browserless backend for: {url}")
        
        try:
            # Try /content API first (faster, cheaper)
            html = await self._fetch_browserless_content(url)
            
            # Check for Cloudflare challenge
            if self._is_cloudflare_in_html(html):
                logger.info(f"Cloudflare detected, retrying with /unblock API: {url}")
                html = await self._fetch_browserless_unblock(url)
                
                # Check again after /unblock
                if self._is_cloudflare_in_html(html):
                    raise ExtractionError(
                        f"Cloudflare challenge could not be bypassed for: {url}"
                    )
            
            if not html or len(html) < 100:
                raise ExtractionError(f"Empty or minimal content from: {url}")
            
            # Extract content using Trafilatura
            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=False,
                output_format="txt",
            )
            
            if not text or len(text.strip()) < 100:
                raise ExtractionError(
                    f"Could not extract meaningful content from: {url}"
                )
            
            # Extract metadata
            metadata = trafilatura.extract_metadata(html, default_url=url)
            
            return self._create_content_from_browser(url, text, metadata)
            
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Browserless extraction failed: {e}") from e

    async def _extract_via_agent_browser(self, url: str) -> ExtractedContent:
        """Extract content using agent-browser CLI with stealth mode.

        Args:
            url: URL of the page to extract.

        Returns:
            ExtractedContent with page text and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        logger.info(f"Using agent-browser backend for: {url}")
        
        try:
            # Set viewport for more human-like behavior
            viewport = random.choice(VIEWPORTS)
            await self._run_cmd_async("set", "viewport", str(viewport["width"]), str(viewport["height"]))
            
            # Add a small random delay to appear more human-like
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Navigate to the page
            await self._run_cmd_async("open", url)
            
            # Wait for network to settle
            try:
                await self._run_cmd_async("wait", "--load", "networkidle", timeout=10)
            except ExtractionError:
                logger.debug("networkidle timeout, continuing with current state")
            
            # Check for Cloudflare challenge
            if await self._is_cloudflare_challenge():
                challenge_resolved = await self._wait_for_cloudflare_challenge()
                if not challenge_resolved:
                    raise ExtractionError(
                        f"Cloudflare challenge could not be bypassed for: {url}"
                    )
            
            # Wait for dynamic content
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Simulate human-like behavior - mouse movement
            try:
                await self._run_cmd_async(
                    "mouse", "move", 
                    str(random.randint(100, 500)), 
                    str(random.randint(100, 400))
                )
                await asyncio.sleep(random.uniform(0.3, 0.7))
            except ExtractionError:
                pass  # Mouse movement is optional
            
            # Scroll to trigger lazy loading
            try:
                await self._run_cmd_async("scroll", "down", "500")
                await asyncio.sleep(random.uniform(0.5, 1.0))
                await self._run_cmd_async("scroll", "up", "500")
            except ExtractionError:
                pass  # Scrolling is optional
            
            # Final Cloudflare check
            if await self._is_cloudflare_challenge():
                raise ExtractionError(
                    f"Still on Cloudflare challenge page after waiting: {url}"
                )
            
            # Get the page HTML
            html_result = await self._run_cmd_async("get", "html", "body")
            html = html_result.get("data", {}).get("html", "")
            
            if not html or len(html) < 100:
                raise ExtractionError(f"Empty or minimal content from: {url}")
            
            # Extract content using Trafilatura
            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=False,
                output_format="txt",
            )
            
            if not text or len(text.strip()) < 100:
                raise ExtractionError(
                    f"Could not extract meaningful content from: {url}"
                )
            
            # Extract metadata
            metadata = trafilatura.extract_metadata(html, default_url=url)
            
            return self._create_content_from_browser(url, text, metadata)
            
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Browser extraction failed: {e}") from e
        finally:
            # Close the session to clean up
            await self.close()

    async def extract(self, url: str) -> ExtractedContent:
        """Extract content using the best available browser backend.
        
        Automatically selects between:
        - agent-browser CLI (when installed)
        - Browserless.io API (fallback for cloud environments)

        Args:
            url: URL of the page to extract.

        Returns:
            ExtractedContent with page text and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        if _is_agent_browser_available():
            return await self._extract_via_agent_browser(url)
        else:
            return await self._extract_via_browserless(url)

    def _create_content_from_browser(
        self,
        url: str,
        text: str,
        metadata: Optional[trafilatura.metadata.Document],
    ) -> ExtractedContent:
        """Create ExtractedContent from browser extraction results."""
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

        return self._create_content(
            url=url,
            raw_text=text,
            title=title,
            author=author,
            published_date=published_date,
            site_name=site_name,
            fallback_used=True,  # Browser is always a fallback method
        )
