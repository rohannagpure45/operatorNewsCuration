"""Browser-based content extractor using Playwright for sites that block httpx."""

import asyncio
import random
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import trafilatura

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType

# User agents to rotate through for stealth
USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    ),
]

# Common viewport sizes
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]


class BrowserExtractor(BaseExtractor):
    """
    Extract content from websites using Playwright browser automation.
    
    This extractor is designed as a fallback for sites that block httpx requests
    with 403 errors or require JavaScript rendering. It uses stealth techniques
    to avoid bot detection.
    """

    url_type = URLType.NEWS_ARTICLE
    extraction_method = "playwright_browser"

    def __init__(self, timeout: int = 60, headless: bool = True):
        """
        Initialize the browser extractor.
        
        Args:
            timeout: Maximum time to wait for page load in seconds.
            headless: Whether to run the browser in headless mode.
        """
        super().__init__(timeout)
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._using_browserless = False

    async def _ensure_browser(self):
        """Ensure the browser is launched and ready."""
        if self._browser is None or not self._browser.is_connected():
            # Clean up disconnected browser before creating new one
            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception:
                    pass  # Ignore errors closing already-disconnected browser
                self._browser = None

            from playwright.async_api import async_playwright

            from src.config import get_settings

            settings = get_settings()

            if self._playwright is None:
                self._playwright = await async_playwright().start()

            if settings.browserless_api_key:
                # Use Browserless.io cloud browser for better anti-detection
                ws_endpoint = f"wss://chrome.browserless.io?token={settings.browserless_api_key}"
                try:
                    self._browser = await self._playwright.chromium.connect_over_cdp(ws_endpoint)
                    self._using_browserless = True
                except Exception:
                    # Sanitize error to avoid leaking API key in logs/exceptions
                    raise ExtractionError(
                        "Failed to connect to Browserless remote browser"
                    ) from None
            else:
                # Fall back to local Playwright with stealth settings
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                self._using_browserless = False

        return self._browser

    async def close(self) -> None:
        """Close the browser and playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

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

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract content using Playwright browser.

        Args:
            url: URL of the page to extract.

        Returns:
            ExtractedContent with page text and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        try:
            browser = await self._ensure_browser()

            # Create context with stealth settings
            user_agent = random.choice(USER_AGENTS)
            viewport = random.choice(VIEWPORTS)

            context = await browser.new_context(
                user_agent=user_agent,
                viewport=viewport,
                locale="en-US",
                timezone_id="America/New_York",
                java_script_enabled=True,
                # Disable webdriver detection
                extra_http_headers={
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/webp,image/apng,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
            )

            # Additional stealth: remove webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Overwrite the plugins array
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Overwrite the languages property
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Pass Chrome test
                window.chrome = {
                    runtime: {}
                };
            """)

            page = await context.new_page()

            try:
                # Add a small random delay to appear more human-like
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Navigate to the page
                response = await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=self.timeout * 1000,
                )

                if response is None:
                    raise ExtractionError(f"Failed to navigate to URL: {url}")

                if response.status == 403:
                    raise ExtractionError(
                        f"Access denied (403) even with browser: {url}"
                    )

                if response.status >= 400:
                    raise ExtractionError(
                        f"HTTP error {response.status} for URL: {url}"
                    )

                # Wait a bit for any dynamic content
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # Scroll down to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(0.5)
                await page.evaluate("window.scrollTo(0, 0)")

                # Get the rendered HTML
                html = await page.content()

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
                metadata = trafilatura.extract_metadata(html, url=url)

                return self._create_content_from_browser(url, text, metadata)

            finally:
                await page.close()
                await context.close()

        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Browser extraction failed: {e}") from e

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

