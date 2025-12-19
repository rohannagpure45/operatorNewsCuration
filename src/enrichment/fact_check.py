"""Fact-checking integration using Google Fact Check Tools API."""

import re
from datetime import datetime
from typing import List, Optional

import httpx

from src.config import get_settings
from src.models.schemas import (
    ClaimRating,
    FactCheckReport,
    FactCheckResult,
    PublisherCredibility,
)


class FactCheckError(Exception):
    """Raised when fact-checking fails."""

    pass


class FactChecker:
    """
    Fact-check claims using Google Fact Check Tools API.
    
    The Google Fact Check Tools API aggregates fact-checks from:
    - PolitiFact
    - Snopes
    - FactCheck.org
    - AFP Fact Check
    - Reuters Fact Check
    - And many more...
    
    It's free to use and doesn't require billing to be enabled.
    """

    # Google Fact Check API endpoint
    API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    # Map fact-check ratings to our schema
    RATING_MAP = {
        "true": ClaimRating.TRUE,
        "mostly true": ClaimRating.MOSTLY_TRUE,
        "half true": ClaimRating.MIXED,
        "mixed": ClaimRating.MIXED,
        "mostly false": ClaimRating.MOSTLY_FALSE,
        "false": ClaimRating.FALSE,
        "pants on fire": ClaimRating.FALSE,
        "incorrect": ClaimRating.FALSE,
        "misleading": ClaimRating.MOSTLY_FALSE,
        "unproven": ClaimRating.UNVERIFIED,
        "outdated": ClaimRating.MIXED,
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """Initialize the fact checker."""
        settings = get_settings()
        self.api_key = api_key or settings.google_fact_check_api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def check_claim(self, claim: str) -> List[FactCheckResult]:
        """
        Search for fact-checks related to a specific claim.

        Args:
            claim: The claim text to search for.

        Returns:
            List of fact-check results.
        """
        if not self.api_key:
            return []

        try:
            client = await self.get_client()

            response = await client.get(
                self.API_URL,
                params={
                    "key": self.api_key,
                    "query": claim,
                    "languageCode": "en",
                },
            )

            if response.status_code != 200:
                return []

            data = response.json()
            claims = data.get("claims", [])

            results = []
            for claim_data in claims:
                result = self._parse_claim_review(claim_data)
                if result:
                    results.append(result)

            return results

        except Exception:
            return []

    def _parse_claim_review(self, claim_data: dict) -> Optional[FactCheckResult]:
        """Parse a claim review from the API response."""
        try:
            claim_text = claim_data.get("text", "")
            reviews = claim_data.get("claimReview", [])

            if not reviews:
                return None

            # Use the first (usually most relevant) review
            review = reviews[0]
            publisher = review.get("publisher", {})

            # Parse rating
            rating_text = review.get("textualRating", "").lower()
            rating = self._map_rating(rating_text)

            # Parse date
            reviewed_date = None
            date_str = review.get("reviewDate")
            if date_str:
                try:
                    reviewed_date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            return FactCheckResult(
                claim=claim_text,
                rating=rating,
                source=publisher.get("name", "Unknown"),
                source_url=review.get("url"),
                explanation=review.get("textualRating"),
                reviewed_date=reviewed_date,
            )

        except Exception:
            return None

    def _map_rating(self, rating_text: str) -> ClaimRating:
        """Map a textual rating to our ClaimRating enum."""
        rating_lower = rating_text.lower().strip()

        # Check for exact matches first
        if rating_lower in self.RATING_MAP:
            return self.RATING_MAP[rating_lower]

        # Check for partial matches using word boundaries
        for key, value in self.RATING_MAP.items():
            if re.search(rf"\b{re.escape(key)}\b", rating_lower):
                return value

        # Default to unverified if we can't parse the rating
        return ClaimRating.UNVERIFIED

    async def check_content(
        self,
        content: str,
        max_claims: int = 5,
    ) -> FactCheckReport:
        """
        Extract and fact-check claims from content.

        Args:
            content: The full text content to analyze.
            max_claims: Maximum number of claims to check.

        Returns:
            FactCheckReport with all results.
        """
        # Extract potential claims from content
        claims = self._extract_claims(content)[:max_claims]

        verified_claims = []
        unverified_claims = []

        for claim in claims:
            results = await self.check_claim(claim)
            if results:
                verified_claims.extend(results)
            else:
                unverified_claims.append(claim)

        return FactCheckReport(
            claims_analyzed=len(claims),
            verified_claims=verified_claims,
            unverified_claims=unverified_claims,
        )

    def _extract_claims(self, content: str) -> List[str]:
        """
        Extract checkable claims from content.
        
        This is a simple heuristic-based extraction. For better results,
        use an LLM to identify claims worth checking.
        """
        claims = []

        # Split into sentences
        sentences = re.split(r"[.!?]+", content)

        for sentence in sentences:
            sentence = sentence.strip()

            # Skip very short or very long sentences
            if len(sentence) < 20 or len(sentence) > 300:
                continue

            # Look for claim indicators
            claim_indicators = [
                r"\b(according to|reports? say|studies? show|research shows?)\b",
                r"\b(percent|%|\d+\s*(million|billion|trillion))\b",
                r"\b(increased|decreased|grew|fell|rose|dropped)\b",
                r"\b(announced|claimed|stated|said|confirmed)\b",
                r"\b(will|would|could|should|must)\b.*\b(happen|occur|result)\b",
            ]

            for pattern in claim_indicators:
                if re.search(pattern, sentence, re.IGNORECASE):
                    claims.append(sentence)
                    break

        return claims


class ClaimBusterChecker:
    """
    Optional integration with ClaimBuster API for claim-worthiness scoring.
    
    ClaimBuster uses AI to determine which claims are worth fact-checking.
    Requires a paid subscription ($50/month).
    """

    API_URL = "https://idir.uta.edu/claimbuster/api/v2/score/text/"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """Initialize ClaimBuster checker."""
        settings = get_settings()
        self.api_key = api_key or settings.claimbuster_api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def score_claims(self, text: str) -> List[dict]:
        """
        Score text for claim-worthiness.

        Args:
            text: Text to analyze.

        Returns:
            List of scored sentences with claim-worthiness scores.
        """
        if not self.api_key:
            return []

        try:
            client = await self.get_client()

            response = await client.post(
                self.API_URL,
                headers={"x-api-key": self.api_key},
                json={"input_text": text},
            )

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get("results", [])

        except Exception:
            return []

    async def get_top_claims(
        self,
        text: str,
        threshold: float = 0.5,
        max_claims: int = 5,
    ) -> List[str]:
        """
        Get top claims worth fact-checking.

        Args:
            text: Text to analyze.
            threshold: Minimum score threshold (0-1).
            max_claims: Maximum number of claims to return.

        Returns:
            List of claim strings sorted by claim-worthiness.
        """
        results = await self.score_claims(text)

        # Filter and sort by score
        worthy_claims = [
            r for r in results
            if r.get("score", 0) >= threshold
        ]
        worthy_claims.sort(key=lambda x: x.get("score", 0), reverse=True)

        return [
            claim_text for c in worthy_claims[:max_claims]
            if (claim_text := c.get("text", ""))
        ]
