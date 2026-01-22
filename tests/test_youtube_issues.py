
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.extractors.youtube import YouTubeExtractor


class TestYouTubeIssues:
    """Tests for specific CodeRabbit issues in YouTubeExtractor."""

    @pytest.fixture
    def extractor(self):
        return YouTubeExtractor()

    def test_get_video_id_prioritize_v_param(self, extractor):
        """Test that 'v' parameter is prioritized over 'video_id'."""
        # Case 1: Only v present
        url1 = "https://www.youtube.com/watch?v=12345678901"
        assert extractor._get_video_id(url1) == "12345678901"

        # Case 2: Only video_id present
        url2 = "https://www.youtube.com/watch?video_id=12345678901"
        assert extractor._get_video_id(url2) == "12345678901"

        # Case 3: Both present, v should take precedence (or at least be found)
        # Note: The implementation detail might be `v` OR `video_id`.
        # If we want to strictly prioritize `v`, if `v` is present it should be used.
        url3 = "https://www.youtube.com/watch?v=REALID12345&video_id=FAKEID54321"
        assert extractor._get_video_id(url3) == "REALID12345"

        # Case 4: Both present, v is prioritized even if it comes second in query?
        # parse_qs order usually doesn't strictly matter for dictionary access, 
        # but the logic `get('v') or get('video_id')` ensures v is checked first.
        url4 = "https://www.youtube.com/watch?video_id=FAKEID54321&v=REALID12345"
        assert extractor._get_video_id(url4) == "REALID12345"

    def test_get_video_id_embed_validation(self, extractor):
        """Test validation of video ID in /embed/ and /v/ paths."""
        # Valid embed
        url1 = "https://www.youtube.com/embed/12345678901"
        assert extractor._get_video_id(url1) == "12345678901"

        # Invalid embed (empty ID)
        url2 = "https://www.youtube.com/embed/"
        assert extractor._get_video_id(url2) is None
        
        # Valid v
        url3 = "https://www.youtube.com/v/12345678901"
        assert extractor._get_video_id(url3) == "12345678901"

        # Invalid v (empty ID)
        url4 = "https://www.youtube.com/v/"
        assert extractor._get_video_id(url4) is None

    @pytest.mark.asyncio
    async def test_extract_empty_transcript_list(self, extractor):
        """Test handling of empty transcript list to prevent IndexError."""
        with patch('src.extractors.youtube.YouTubeTranscriptApi') as MockApi:
            mock_api_instance = MockApi.return_value
            # list returns an empty list
            mock_api_instance.list.return_value = []
            
            # Mock browser extractor to avoid actual network call and speed up test
            extractor.browser_extractor.extract = MagicMock()
            f = asyncio.Future()
            f.set_result("Mock fallback content")
            extractor.browser_extractor.extract.return_value = f

            # Should not raise IndexError
            url = "https://www.youtube.com/watch?v=12345678901"
            await extractor.extract(url)
            
            # Should have fallen back to browser extractor
            extractor.browser_extractor.extract.assert_called_once()
