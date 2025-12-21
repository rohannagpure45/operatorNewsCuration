"""Twitter/X content extractor using syndication API."""

import re
from datetime import datetime
from typing import Optional

import httpx

from src.extractors.base import BaseExtractor, ExtractionError
from src.models.schemas import ExtractedContent, URLType


class TwitterExtractor(BaseExtractor):
    """
    Extract content from Twitter/X using the syndication API.
    
    This uses the same API that Twitter's embedded tweets use,
    which doesn't require authentication.
    """

    url_type = URLType.TWITTER
    extraction_method = "twitter_syndication"

    # Syndication API endpoint (used by embedded tweets)
    SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result"

    def can_handle(self, url: str) -> bool:
        """Check if this is a Twitter/X URL."""
        patterns = [
            r"^https?://(www\.)?(twitter|x)\.com/\w+/status/\d+",
            r"^https?://(mobile\.)?(twitter|x)\.com/\w+/status/\d+",
        ]
        return any(re.match(p, url.lower()) for p in patterns)

    def _extract_tweet_id(self, url: str) -> Optional[str]:
        """Extract tweet ID from URL."""
        match = re.search(r"/status/(\d+)", url)
        return match.group(1) if match else None

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract tweet content using syndication API.

        Args:
            url: Twitter/X status URL.

        Returns:
            ExtractedContent with tweet text and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        tweet_id = self._extract_tweet_id(url)
        if not tweet_id:
            raise ExtractionError(f"Could not extract tweet ID from URL: {url}")

        try:
            client = await self.get_client()

            # Fetch tweet data from syndication API
            response = await client.get(
                self.SYNDICATION_URL,
                params={
                    "id": tweet_id,
                    "token": self._generate_token(tweet_id),
                },
                headers={
                    "Accept": "application/json",
                    "Referer": "https://platform.twitter.com/",
                },
            )

            if response.status_code == 404:
                raise ExtractionError(f"Tweet not found: {url}")

            if response.status_code != 200:
                raise ExtractionError(
                    f"Failed to fetch tweet (status {response.status_code}): {url}"
                )

            data = response.json()
            return self._parse_tweet_data(url, data)

        except httpx.RequestError as e:
            raise ExtractionError(f"Network error fetching tweet: {e}") from e
        except Exception as e:
            if isinstance(e, ExtractionError):
                raise
            raise ExtractionError(f"Error extracting tweet: {e}") from e

    def _generate_token(self, tweet_id: str) -> str:
        """
        Generate a token for the syndication API.
        
        The token is derived from the tweet ID using a simple algorithm.
        """
        # This is a simplified token generation - the actual Twitter
        # implementation uses a more complex method, but this works
        # for most public tweets
        return str(int(tweet_id) // 10 ** (len(tweet_id) - 1))

    def _parse_tweet_data(self, url: str, data: dict) -> ExtractedContent:
        """Parse tweet JSON data into ExtractedContent."""
        # Extract main text
        text = data.get("text", "")

        # Handle quoted tweets and threads
        if "quoted_tweet" in data:
            quoted = data["quoted_tweet"]
            quoted_text = quoted.get("text", "")
            quoted_user = quoted.get("user", {}).get("name", "Unknown")
            text += f"\n\n[Quoting @{quoted_user}]: {quoted_text}"

        # Extract author info
        user = data.get("user", {})
        author = user.get("name", "Unknown")
        username = user.get("screen_name", "")
        if username:
            author = f"{author} (@{username})"

        # Parse creation date
        published_date = None
        created_at = data.get("created_at")
        if created_at:
            try:
                # Twitter date format: "Wed Oct 10 20:19:24 +0000 2018"
                published_date = datetime.strptime(
                    created_at, "%a %b %d %H:%M:%S %z %Y"
                )
            except ValueError:
                pass

        # Build rich text with context
        full_text = self._build_full_text(data, text, author)

        return self._create_content(
            url=url,
            raw_text=full_text,
            title=f"Tweet by {author}",
            author=author,
            published_date=published_date,
            site_name="Twitter/X",
            language=data.get("lang", "en"),
        )

    def _build_full_text(self, data: dict, text: str, author: str) -> str:
        """Build full text including media descriptions and engagement."""
        parts = [text]

        # Add media descriptions if present
        photos = data.get("photos", [])
        if photos:
            parts.append(f"\n[{len(photos)} image(s) attached]")

        videos = data.get("video", {})
        if videos:
            parts.append("\n[Video attached]")

        # Add engagement metrics for context
        favorite_count = data.get("favorite_count", 0)
        retweet_count = data.get("retweet_count", 0)
        reply_count = data.get("reply_count", 0)

        if any([favorite_count, retweet_count, reply_count]):
            parts.append(
                f"\n\n[Engagement: {favorite_count:,} likes, "
                f"{retweet_count:,} retweets, {reply_count:,} replies]"
            )

        return "\n".join(parts)

