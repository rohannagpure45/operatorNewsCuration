"""YouTube content extractor using youtube-transcript-api."""

import asyncio
import logging
from typing import Optional
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from src.extractors.base import BaseExtractor, ExtractedContent
from src.extractors.browser import BrowserExtractor

logger = logging.getLogger(__name__)


class YouTubeExtractor(BaseExtractor):
    """
    Extracts content from YouTube videos, prioritizing transcripts.
    Falls back to basic metadata extraction via BrowserExtractor if transcript fails.
    """

    def __init__(self, timeout: int = 60):
        """
        Initialize the YouTube extractor.

        Args:
            timeout: Maximum time to wait for operations in seconds.
        """
        super().__init__(timeout)
        self.browser_extractor = BrowserExtractor(timeout=timeout)

    @staticmethod
    def _get_video_id(url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube URL.

        Returns:
            Video ID or None if not found.
        """
        parsed = urlparse(url)
        if parsed.hostname in ("youtu.be", "www.youtu.be"):
            return parsed.path[1:]
        if parsed.hostname in ("youtube.com", "www.youtube.com"):
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [None])[0] or parse_qs(parsed.query).get("video_id", [None])[0]
            if parsed.path.startswith("/embed/"):
                parts = parsed.path.split("/")
                return parts[2] if len(parts) > 2 and parts[2] else None
            if parsed.path.startswith("/v/"):
                parts = parsed.path.split("/")
                return parts[2] if len(parts) > 2 and parts[2] else None
        return None

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract content from a YouTube video URL.
        
        Tries to fetch the transcript. If successful, returns the transcript text.
        If no transcript is available, falls back to the browser extractor to get page metadata.

        Args:
            url: URL of the YouTube video.

        Returns:
            ExtractedContent with transcript or page metadata.
        """
        video_id = self._get_video_id(url)
        
        if not video_id:
            logger.warning(f"Could not extract video ID from {url}, falling back to browser")
            return await self.browser_extractor.extract(url)

        try:
            # Fetch transcript using instance-based API (v1.2.3?)
            api = YouTubeTranscriptApi()
            transcript_list = await asyncio.to_thread(api.list, video_id)
            
            # Try to find English transcript (manual or generated)
            # find_transcript takes a list of language codes
            try:
                transcript = transcript_list.find_transcript(['en'])
            except Exception:
                # If 'en' not found, just take the first available one?
                # Or try iterate. For now let's just try to get the first one if find fails
                # The TranscriptList object is iterable
                found = False
                for t in transcript_list:
                    if t.language_code.startswith('en'):
                        transcript = t
                        found = True
                        break
                if not found:
                    transcripts = list(transcript_list)
                    if not transcripts:
                        raise ValueError("No transcripts available")
                    # Just take the first one
                    transcript = transcripts[0]

            transcript_data = await asyncio.to_thread(transcript.fetch)
            
            # Format transcript
            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript_data)
            
            # We still might want basic metadata (title, etc.)
            # Optimally we would use the YouTube Data API or oEmbed, but for now 
            # let's try to get the title via browser extractor cheaply or just return transcript
            # Fetching page with browser extractor is heavy but gives us the title.
            # Let's do a quick metadata fetch if possible? 
            # Actually, `BrowserExtractor` is heavy (launches browser).
            # Maybe for now, we just return the transcript and let the summarizer handle it.
            # However, the user request example shows "This Morning's Top Headlines..." title.
            # So we probably want the title.
            
            # Let's get metadata via browser extractor concurrently? 
            # Or just accept the cost. The transcript is the most important part.
            # If we just return transcript, we miss the title which is important for "News".
            
            # Strategy: Get metadata from browser extractor first (or concurrently), 
            # then append/replace content with transcript.
            
            logger.info(f"Fetching metadata for video {video_id} via browser")
            metadata_content = await self.browser_extractor.extract(url)
            
            # Combine them
            full_text = f"VIDEO TITLE: {metadata_content.metadata.title}\n\nTRANSCRIPT:\n{transcript_text}"
            
            # Update metadata with our generated text
            metadata_content.raw_text = full_text
            metadata_content.metadata.word_count = len(full_text.split())
            
            return metadata_content

        except Exception as e:
            logger.warning(f"Failed to fetch transcript for {video_id}: {e}")
            logger.info("Falling back to browser extraction only")
            return await self.browser_extractor.extract(url)

    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle the URL.
        
        Args:
            url: URL to check.
            
        Returns:
            True if it's a valid YouTube URL.
        """
        return self._get_video_id(url) is not None

    async def close(self):
        """Close resources."""
        await self.browser_extractor.close()
