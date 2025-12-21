"""Wayback Machine fallback for accessing archived content."""

import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx


class WaybackError(Exception):
    """Raised when Wayback Machine access fails."""

    pass


class WaybackFetcher:
    """
    Fetch archived versions of URLs from the Wayback Machine.
    
    Useful for:
    - Soft-paywalled content that was previously accessible
    - Content that has been removed or modified
    - Bypassing some JavaScript-heavy sites
    """

    # Wayback Machine API endpoints
    AVAILABILITY_API = "https://archive.org/wayback/available"
    CDX_API = "https://web.archive.org/cdx/search/cdx"

    def __init__(self, timeout: int = 30):
        """Initialize the Wayback fetcher."""
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "NewsCurationAgent/1.0 "
                        "(https://github.com/your-org/operatorNewsCuration)"
                    ),
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_archived_url(self, url: str) -> Optional[str]:
        """
        Get the most recent archived URL for the given URL.

        Args:
            url: The original URL to look up.

        Returns:
            Wayback Machine URL for the archived version, or None if not found.
        """
        try:
            client = await self.get_client()

            # Use availability API first (faster)
            response = await client.get(
                self.AVAILABILITY_API,
                params={"url": url},
            )

            if response.status_code == 200:
                data = response.json()
                snapshots = data.get("archived_snapshots", {})
                closest = snapshots.get("closest", {})

                if closest.get("available"):
                    return closest.get("url")

            return None

        except Exception:
            return None

    async def get_best_snapshot(
        self,
        url: str,
        prefer_recent: bool = True,
        max_age_days: Optional[int] = 365,
    ) -> Optional[str]:
        """
        Get the best available snapshot URL.

        Args:
            url: The original URL.
            prefer_recent: Prefer more recent snapshots.
            max_age_days: Maximum age of snapshot in days (None for no limit).

        Returns:
            Wayback Machine URL or None.
        """
        try:
            client = await self.get_client()

            # Use CDX API for more control
            params = {
                "url": url,
                "output": "json",
                "limit": 5,
                "filter": "statuscode:200",
            }

            if prefer_recent:
                params["sort"] = "reverse"  # Most recent first

            response = await client.get(self.CDX_API, params=params)

            if response.status_code != 200:
                return None

            lines = response.json()
            if len(lines) < 2:  # First line is header
                return None

            # Parse results (skip header row)
            for row in lines[1:]:
                if len(row) >= 3:
                    timestamp = row[1]
                    original_url = row[2]

                    # Check age if specified
                    if max_age_days:
                        try:
                            snapshot_date = datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                            age = (datetime.now(timezone.utc) - snapshot_date).days
                            if age > max_age_days:
                                continue
                        except ValueError:
                            pass

                    # Construct Wayback URL
                    return f"https://web.archive.org/web/{timestamp}/{original_url}"

            return None

        except Exception:
            return None

    async def fetch_archived_content(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from Wayback Machine.

        Args:
            url: The original URL to fetch archived version of.

        Returns:
            HTML content from the archived version, or None if not available.
        """
        archived_url = await self.get_archived_url(url)
        if not archived_url:
            archived_url = await self.get_best_snapshot(url)

        if not archived_url:
            return None

        try:
            client = await self.get_client()
            response = await client.get(archived_url)

            if response.status_code == 200:
                # Remove Wayback Machine toolbar/banner from HTML
                html = self._clean_wayback_html(response.text)
                return html

            return None

        except Exception:
            return None

    def _clean_wayback_html(self, html: str) -> str:
        """Remove Wayback Machine injected elements from HTML."""
        # Remove Wayback banner/toolbar comment blocks
        html = re.sub(
            r"<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?<!-- END WAYBACK TOOLBAR INSERT -->",
            "",
            html,
            flags=re.DOTALL,
        )

        # Remove Wayback scripts
        html = re.sub(
            r'<script[^>]*src="[^"]*archive\.org[^"]*"[^>]*>.*?</script>',
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Fix URLs that point to Wayback versions
        html = re.sub(
            r'(href|src)="https?://web\.archive\.org/web/\d+/',
            r'\1="',
            html,
        )

        return html

    async def is_available(self, url: str) -> bool:
        """
        Check if an archived version is available.

        Args:
            url: The URL to check.

        Returns:
            True if an archived version exists.
        """
        archived_url = await self.get_archived_url(url)
        return archived_url is not None

