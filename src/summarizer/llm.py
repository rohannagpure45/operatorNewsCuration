"""LLM-based summarization using Gemini with Instructor."""

import asyncio
import json
import time
from typing import List, Optional

import google.generativeai as genai
import instructor

from src.config import get_settings
from src.models.schemas import (
    ContentSummary,
    ExtractedContent,
)
from src.summarizer.prompts import (
    CLAIM_EXTRACTION_PROMPT,
    SUMMARIZATION_SYSTEM_PROMPT,
    SUMMARIZATION_USER_PROMPT,
)


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, requests_per_minute: int = 5):
        """Initialize rate limiter with requests per minute limit."""
        self.rpm = requests_per_minute
        self.interval = 60.0 / requests_per_minute  # seconds between requests
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until we can make another request."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                await asyncio.sleep(wait_time)
            self._last_request = time.time()

    def acquire_sync(self) -> None:
        """Synchronous version of acquire."""
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.interval:
            wait_time = self.interval - elapsed
            time.sleep(wait_time)
        self._last_request = time.time()


# Global rate limiter for Gemini API (free tier: 5 RPM)
_gemini_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(rpm: int = 4) -> RateLimiter:
    """Get or create global rate limiter."""
    global _gemini_rate_limiter
    if _gemini_rate_limiter is None:
        _gemini_rate_limiter = RateLimiter(requests_per_minute=rpm)
    return _gemini_rate_limiter


class SummarizationError(Exception):
    """Raised when summarization fails."""

    pass


class Summarizer:
    """
    Generate structured summaries using Gemini LLM with Instructor.
    
    Uses the Instructor library to ensure structured, schema-validated output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize the summarizer with Gemini."""
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model or settings.gemini_model

        if not self.api_key:
            raise SummarizationError("Gemini API key is required")

        # Configure Gemini
        genai.configure(api_key=self.api_key)

        # Create Instructor-wrapped client
        self.client = instructor.from_gemini(
            client=genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Lower temperature for more consistent output
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=4096,
                ),
            ),
            mode=instructor.Mode.GEMINI_JSON,
        )

    def summarize(
        self,
        content: ExtractedContent,
    ) -> ContentSummary:
        """
        Generate a structured summary of the extracted content.

        Args:
            content: The extracted content to summarize.

        Returns:
            ContentSummary with structured summary data.

        Raises:
            SummarizationError: If summarization fails.
        """
        try:
            # Prepare the prompt
            user_prompt = SUMMARIZATION_USER_PROMPT.format(
                url=content.url,
                source_type=content.url_type.value,
                title=content.metadata.title or "Unknown",
                author=content.metadata.author or "Unknown",
                published_date=(
                    content.metadata.published_date.isoformat()
                    if content.metadata.published_date
                    else "Unknown"
                ),
                content=self._truncate_content(content.raw_text),
            )

            # Generate structured summary
            summary = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_model=ContentSummary,
            )

            return summary

        except Exception as e:
            raise SummarizationError(f"Failed to generate summary: {e}") from e

    def extract_claims(
        self,
        content: str,
        max_claims: int = 5,
    ) -> List[str]:
        """
        Extract checkable claims from content for fact-checking.

        Args:
            content: The text content to analyze.
            max_claims: Maximum number of claims to extract.

        Returns:
            List of claim strings. Returns empty list on failure.
        """
        try:
            prompt = CLAIM_EXTRACTION_PROMPT.format(
                content=self._truncate_content(content),
                max_claims=max_claims,
            )

            # Use raw Gemini for simpler output
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                ),
            )

            # Parse the response as JSON array
            text = response.text.strip()

            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            claims = json.loads(text)

            if isinstance(claims, list):
                return [str(c) for c in claims[:max_claims]]

            return []

        except Exception as e:
            # Fallback to empty list if extraction fails
            return []

    def _truncate_content(self, content: str, max_tokens: int = 30000) -> str:
        """
        Truncate content to fit within token limits.
        
        Rough estimate: 1 token ≈ 4 characters for English text.
        """
        max_chars = max_tokens * 4

        if len(content) <= max_chars:
            return content

        # Truncate and add indicator
        truncated = content[: max_chars - 100]

        # Try to end at a sentence boundary
        last_period = truncated.rfind(".")
        if last_period > max_chars * 0.8:
            truncated = truncated[: last_period + 1]

        return truncated + "\n\n[Content truncated due to length...]"


class AsyncSummarizer(Summarizer):
    """
    Async wrapper for Summarizer for better integration with async code.
    
    Note: The underlying Gemini SDK is synchronous, so we use asyncio.to_thread
    for true async behavior in production.
    """

    def __init__(self, *args, rate_limit_rpm: int = 4, **kwargs):
        """Initialize with rate limiting."""
        super().__init__(*args, **kwargs)
        self.rate_limiter = get_rate_limiter(rate_limit_rpm)

    async def close(self) -> None:
        """Close any resources (no-op for Summarizer, but needed for API compatibility)."""
        pass

    async def summarize(
        self,
        content: ExtractedContent,
    ) -> ContentSummary:
        """Async version of summarize with rate limiting."""
        # Wait for rate limit
        await self.rate_limiter.acquire()

        # Run sync method in thread pool
        return await asyncio.to_thread(
            self._summarize_sync,
            content,
        )

    def _summarize_sync(
        self,
        content: ExtractedContent,
    ) -> ContentSummary:
        """Synchronous summarization for thread pool execution."""
        try:
            user_prompt = SUMMARIZATION_USER_PROMPT.format(
                url=content.url,
                source_type=content.url_type.value,
                title=content.metadata.title or "Unknown",
                author=content.metadata.author or "Unknown",
                published_date=(
                    content.metadata.published_date.isoformat()
                    if content.metadata.published_date
                    else "Unknown"
                ),
                content=self._truncate_content(content.raw_text),
            )

            summary = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_model=ContentSummary,
            )

            return summary

        except Exception as e:
            raise SummarizationError(f"Failed to generate summary: {e}") from e

    async def extract_claims(
        self,
        content: str,
        max_claims: int = 5,
    ) -> List[str]:
        """Async version of extract_claims with rate limiting."""
        # Wait for rate limit
        await self.rate_limiter.acquire()

        return await asyncio.to_thread(
            self._extract_claims_sync,
            content,
            max_claims,
        )

    def _extract_claims_sync(
        self,
        content: str,
        max_claims: int = 5,
    ) -> List[str]:
        """Synchronous claim extraction for thread pool execution."""
        try:
            prompt = CLAIM_EXTRACTION_PROMPT.format(
                content=self._truncate_content(content),
                max_claims=max_claims,
            )

            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                ),
            )

            text = response.text.strip()

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            claims = json.loads(text)

            if isinstance(claims, list):
                return [str(c) for c in claims[:max_claims]]

            return []

        except Exception:
            return []


