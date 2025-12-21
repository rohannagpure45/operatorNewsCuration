"""SEC filings extractor for 13F and other SEC documents."""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType


class SECExtractor(BaseExtractor):
    """
    Extract content from SEC filings and 13F data.
    
    Supports:
    - sec.gov filing pages
    - 13f.info structured data
    """

    url_type = URLType.SEC_FILING
    extraction_method = "sec_parser"

    def can_handle(self, url: str) -> bool:
        """Check if this is an SEC-related URL."""
        patterns = [
            r"^https?://(www\.)?sec\.gov/",
            r"^https?://(www\.)?13f\.info/",
            r"^https?://(www\.)?secfilings\.nasdaq\.com/",
        ]
        return any(re.match(p, url.lower()) for p in patterns)

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract SEC filing content.

        Args:
            url: URL of the SEC filing.

        Returns:
            ExtractedContent with filing data and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        try:
            client = await self.get_client()
            response = await client.get(url)

            if response.status_code != 200:
                raise ExtractionError(
                    f"Failed to fetch SEC filing (status {response.status_code}): {url}"
                )

            html = response.text
            parsed = urlparse(url)

            if "13f.info" in parsed.netloc:
                return await self._extract_13f_info(url, html)
            elif "sec.gov" in parsed.netloc:
                return await self._extract_sec_gov(url, html)
            else:
                return await self._extract_generic_filing(url, html)

        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Error extracting SEC filing: {e}") from e

    async def _extract_13f_info(self, url: str, html: str) -> ExtractedContent:
        """Extract data from 13f.info structured pages."""
        soup = BeautifulSoup(html, "lxml")

        # Extract fund/manager name
        title_elem = soup.find("h1") or soup.find("title")
        title = title_elem.get_text(strip=True) if title_elem else "13F Filing"

        # Extract holdings table
        holdings_text = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if cells:
                    row_text = " | ".join(c.get_text(strip=True) for c in cells)
                    holdings_text.append(row_text)

        # Extract summary info
        summary_parts = []

        # Look for key metrics
        for text_pattern in [
            r"Total Value[:\s]+\$?([\d,.]+)",
            r"Number of Holdings[:\s]+(\d+)",
            r"Report Date[:\s]+([\d/\-]+)",
        ]:
            match = re.search(text_pattern, html, re.IGNORECASE)
            if match:
                summary_parts.append(match.group(0))

        # Build full text
        full_text = f"# {title}\n\n"
        if summary_parts:
            full_text += "## Summary\n" + "\n".join(summary_parts) + "\n\n"
        if holdings_text:
            full_text += "## Holdings\n" + "\n".join(holdings_text[:50])  # Limit rows
            if len(holdings_text) > 50:
                full_text += f"\n... and {len(holdings_text) - 50} more holdings"

        return self._create_content(
            url=url,
            raw_text=full_text,
            title=title,
            site_name="13f.info",
        )

    async def _extract_sec_gov(self, url: str, html: str) -> ExtractedContent:
        """Extract data from SEC.gov filing pages."""
        soup = BeautifulSoup(html, "lxml")

        # Extract filing info
        title = "SEC Filing"
        title_elem = soup.find("title")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Try to find the main content
        content_parts = []

        # Look for filing header info
        header = soup.find("div", {"class": "formGrouping"})
        if header:
            content_parts.append(header.get_text(strip=True))

        # Look for the main document content
        main_content = soup.find("div", {"id": "filing-content"})
        if not main_content:
            main_content = soup.find("div", {"class": "filing-content"})
        if not main_content:
            main_content = soup.find("pre")  # Some filings use <pre> tags

        if main_content:
            content_parts.append(main_content.get_text(strip=True))
        else:
            # Fallback: extract all text from body
            body = soup.find("body")
            if body:
                # Remove script and style elements
                for element in body.find_all(["script", "style", "nav", "header", "footer"]):
                    element.decompose()
                content_parts.append(body.get_text(separator="\n", strip=True))

        # Extract metadata
        published_date = None
        date_elem = soup.find("div", {"class": "info"})
        if date_elem:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_elem.get_text())
            if date_match:
                try:
                    published_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                except ValueError:
                    pass

        full_text = "\n\n".join(content_parts)

        # Truncate if too long
        if len(full_text) > 50000:
            full_text = full_text[:50000] + "\n\n[Content truncated...]"

        return self._create_content(
            url=url,
            raw_text=full_text,
            title=title,
            published_date=published_date,
            site_name="SEC.gov",
        )

    async def _extract_generic_filing(self, url: str, html: str) -> ExtractedContent:
        """Generic fallback for SEC-related content."""
        soup = BeautifulSoup(html, "lxml")

        # Remove non-content elements
        for element in soup.find_all(["script", "style", "nav", "header", "footer"]):
            element.decompose()

        # Get title
        title = "SEC Filing"
        title_elem = soup.find("title")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Get body text
        body = soup.find("body")
        full_text = body.get_text(separator="\n", strip=True) if body else ""

        # Truncate if needed
        if len(full_text) > 50000:
            full_text = full_text[:50000] + "\n\n[Content truncated...]"

        return self._create_content(
            url=url,
            raw_text=full_text,
            title=title,
            site_name=urlparse(url).netloc,
        )

