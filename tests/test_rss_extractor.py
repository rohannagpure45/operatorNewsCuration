"""Tests for RSS feed extractor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.extractors.rss import RSSExtractor, extract_from_rss
from src.extractors.base import ExtractionError



# Sample RSS feed content for testing
SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>OpenAI Blog</title>
    <link>https://openai.com/blog</link>
    <description>Updates from OpenAI</description>
    <item>
      <title>Introducing Frontier Science</title>
      <link>https://openai.com/index/frontierscience</link>
      <pubDate>Thu, 19 Dec 2025 12:00:00 GMT</pubDate>
      <author>OpenAI Team</author>
      <description>A short description of the article.</description>
      <content:encoded><![CDATA[
        <p>This is the full article content about Frontier Science.</p>
        <p>It contains multiple paragraphs with detailed information about the new research initiative.</p>
        <p>The research focuses on advancing AI capabilities while ensuring safety.</p>
      ]]></content:encoded>
    </item>
    <item>
      <title>Another Article</title>
      <link>https://openai.com/blog/another-article</link>
      <pubDate>Wed, 18 Dec 2025 10:00:00 GMT</pubDate>
      <description>Description of another article.</description>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Anthropic News</title>
  <link href="https://www.anthropic.com"/>
  <entry>
    <title>Claude 4 Announcement</title>
    <link href="https://www.anthropic.com/news/claude-4"/>
    <published>2025-12-20T09:00:00Z</published>
    <author><name>Anthropic Team</name></author>
    <content type="html">
      &lt;p&gt;We are excited to announce Claude 4, our latest AI assistant.&lt;/p&gt;
      &lt;p&gt;This release includes significant improvements in reasoning and safety.&lt;/p&gt;
    </content>
  </entry>
</feed>
"""


class TestRSSExtractor:
    """Tests for RSSExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create an RSS extractor instance."""
        return RSSExtractor(timeout=30)

    def test_can_handle_any_url(self, extractor):
        """RSS extractor should indicate it can handle any URL."""
        assert extractor.can_handle("https://openai.com/blog/post")
        assert extractor.can_handle("https://example.com/article")

    def test_extract_slug_from_path(self, extractor):
        """Test slug extraction from URL paths."""
        assert extractor._extract_slug("/blog/my-article") == "my-article"
        assert extractor._extract_slug("/index/frontierscience") == "frontierscience"
        assert extractor._extract_slug("/news/announcement") == "announcement"
        assert extractor._extract_slug("/") == ""

    def test_clean_html(self, extractor):
        """Test HTML cleaning removes tags and decodes entities."""
        html = "<p>Hello &amp; World</p><script>alert('x')</script>"
        cleaned = extractor._clean_html(html)
        assert "Hello & World" in cleaned
        assert "<script>" not in cleaned
        assert "<p>" not in cleaned

    @pytest.mark.asyncio
    async def test_extract_from_feed_success(self, extractor):
        """Test successful extraction from RSS feed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_FEED

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.extract_from_feed(
                article_url="https://openai.com/index/frontierscience",
                feed_url="https://openai.com/blog/rss.xml",
            )

            assert result is not None
            assert result.metadata.title == "Introducing Frontier Science"
            assert "Frontier Science" in result.raw_text
            assert result.extraction_method == "rss_feed"
            assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_extract_from_feed_article_not_found(self, extractor):
        """Test extraction fails when article not in feed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_FEED

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract_from_feed(
                    article_url="https://openai.com/blog/nonexistent-article",
                    feed_url="https://openai.com/blog/rss.xml",
                )

            assert "not found in RSS feed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_from_feed_http_error(self, extractor):
        """Test extraction fails on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract_from_feed(
                    article_url="https://openai.com/index/frontierscience",
                    feed_url="https://openai.com/blog/rss.xml",
                )

            assert "status 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_from_atom_feed(self, extractor):
        """Test extraction from Atom feed format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_ATOM_FEED

        with patch.object(extractor, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extractor.extract_from_feed(
                article_url="https://www.anthropic.com/news/claude-4",
                feed_url="https://www.anthropic.com/rss.xml",
            )

            assert result is not None
            assert result.metadata.title == "Claude 4 Announcement"
            assert "Claude 4" in result.raw_text

    def test_find_matching_entry_exact_match(self, extractor):
        """Test finding entry by exact URL match."""
        import feedparser
        feed = feedparser.parse(SAMPLE_RSS_FEED)
        
        entry, score = extractor._find_matching_entry(
            "https://openai.com/index/frontierscience",
            feed.entries,
        )
        
        assert entry is not None
        assert score == 1.0
        assert entry.title == "Introducing Frontier Science"

    def test_find_matching_entry_slug_match(self, extractor):
        """Test finding entry by slug similarity."""
        import feedparser
        feed = feedparser.parse(SAMPLE_RSS_FEED)
        
        # Use a slightly different URL but same slug
        entry, score = extractor._find_matching_entry(
            "https://openai.com/blog/frontierscience",
            feed.entries,
        )
        
        # Should find by slug match
        assert entry is not None
        assert score >= 0.7

    def test_find_matching_entry_no_match(self, extractor):
        """Test no match found for unknown URL."""
        import feedparser
        feed = feedparser.parse(SAMPLE_RSS_FEED)
        
        entry, score = extractor._find_matching_entry(
            "https://openai.com/blog/completely-different-article",
            feed.entries,
        )
        
        assert entry is None
        assert score == 0.0


class TestExtractFromRSSConvenience:
    """Tests for the convenience function."""

    @pytest.mark.asyncio
    async def test_extract_from_rss_function(self):
        """Test the convenience function works."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_FEED

        with patch('src.extractors.rss.RSSExtractor.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await extract_from_rss(
                article_url="https://openai.com/index/frontierscience",
                feed_url="https://openai.com/blog/rss.xml",
            )

            assert result is not None
            assert "Frontier Science" in result.metadata.title

