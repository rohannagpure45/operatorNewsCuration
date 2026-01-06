"""Tests for Slides JSON export functionality.

Tests for SlidesJSONGenerator, SlideType, SlideContent models,
and the unified quote/theme detection logic.
"""

import json
from datetime import datetime, timezone

import pytest

from src.models.schemas import (
    AggregatedResult,
    AggregatedResultSet,
    ContentMetadata,
    ContentSummary,
    Footnote,
    ProcessedResult,
    ProcessingStatus,
    Sentiment,
    SlideContent,
    SlideType,
    SourceReference,
    URLType,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_summary_with_slides():
    """Create sample summary with slide content."""
    return ContentSummary(
        executive_summary="Google announced Gemini 3 Flash, a faster AI model.",
        key_points=[
            "Gemini 3 Flash achieves 90.4% on GPQA benchmark",
            "Model is 3x faster than Gemini 2.5 Pro",
            "API pricing at $0.50 per 1M input tokens",
        ],
        sentiment=Sentiment.POSITIVE,
        topics=["AI", "Google", "LLM"],
        slide_content=SlideContent(
            slide_type=SlideType.BULLETS,
            headline="Google Launches Gemini 3 Flash",
            bullets=[
                "90.4% on GPQA benchmark",
                "3x faster than Gemini 2.5 Pro",
                "API: $0.50/1M input tokens",
            ],
        ),
    )


@pytest.fixture
def sample_summary_with_quote():
    """Create sample summary with quote slide content."""
    return ContentSummary(
        executive_summary="OpenAI CEO discusses AI future.",
        key_points=["AI will transform industries"],
        sentiment=Sentiment.POSITIVE,
        topics=["AI", "OpenAI"],
        footnotes=[
            Footnote(
                id=1,
                source_text="AI will fundamentally change how we work and live in the next decade.",
                context="Sam Altman, CEO of OpenAI",
            ),
        ],
        slide_content=SlideContent(
            slide_type=SlideType.QUOTE,
            headline="OpenAI CEO on AI Future",
            quote_text="AI will fundamentally change how we work and live.",
            quote_attribution="Sam Altman, CEO of OpenAI",
        ),
    )


@pytest.fixture
def processed_result_bullets(sample_summary_with_slides):
    """Create ProcessedResult with bullet slide."""
    return ProcessedResult(
        url="https://blog.google/products/gemini/gemini-3-flash",
        source_type=URLType.NEWS_ARTICLE,
        status=ProcessingStatus.COMPLETED,
        content=ContentMetadata(
            title="Google Launches Gemini 3 Flash",
            site_name="Google Blog",
        ),
        summary=sample_summary_with_slides,
    )


@pytest.fixture
def processed_result_video():
    """Create ProcessedResult with video URL."""
    return ProcessedResult(
        url="https://youtube.com/watch?v=abc123",
        source_type=URLType.NEWS_ARTICLE,
        status=ProcessingStatus.COMPLETED,
        content=ContentMetadata(
            title="Gemini 3 Flash Demo Video",
            site_name="YouTube",
        ),
        summary=ContentSummary(
            executive_summary="Demo video showing Gemini 3 capabilities.",
            key_points=["Shows coding capabilities", "Demonstrates speed"],
            sentiment=Sentiment.POSITIVE,
            topics=["AI", "Google"],
        ),
    )


@pytest.fixture
def aggregated_result():
    """Create AggregatedResult with multiple sources."""
    return AggregatedResult(
        title="Google Launches Gemini 3 Flash",
        sources=[
            SourceReference(
                url="https://blog.google/products/gemini/gemini-3-flash",
                title="Gemini 3 Flash Announcement",
                site_name="Google Blog",
            ),
            SourceReference(
                url="https://x.com/google/status/123",
                title="Google Tweet",
                site_name="Twitter/X",
            ),
        ],
        summary=ContentSummary(
            executive_summary="Google announced Gemini 3 Flash.",
            key_points=["90.4% on GPQA benchmark", "3x faster"],
            sentiment=Sentiment.POSITIVE,
            topics=["AI", "Google", "LLM"],
        ),
        original_count=2,
    )


# ============================================================================
# SlideType and SlideContent Model Tests
# ============================================================================


class TestSlideTypeEnum:
    """Tests for SlideType enum."""

    def test_slide_type_values(self):
        """SlideType enum has expected values."""
        assert SlideType.BULLETS.value == "bullets"
        assert SlideType.QUOTE.value == "quote"
        assert SlideType.VIDEO.value == "video"

    def test_slide_type_from_string(self):
        """Can create SlideType from string value."""
        assert SlideType("bullets") == SlideType.BULLETS
        assert SlideType("quote") == SlideType.QUOTE
        assert SlideType("video") == SlideType.VIDEO


class TestSlideContentModel:
    """Tests for SlideContent model."""

    def test_bullet_slide_content(self):
        """Can create bullet slide content."""
        sc = SlideContent(
            slide_type=SlideType.BULLETS,
            headline="Test Headline",
            bullets=["Point 1", "Point 2", "Point 3"],
        )
        assert sc.slide_type == SlideType.BULLETS
        assert sc.headline == "Test Headline"
        assert len(sc.bullets) == 3

    def test_quote_slide_content(self):
        """Can create quote slide content."""
        sc = SlideContent(
            slide_type=SlideType.QUOTE,
            headline="Quote Headline",
            quote_text="This is a notable quote.",
            quote_attribution="Famous Person, Title",
        )
        assert sc.slide_type == SlideType.QUOTE
        assert sc.quote_text == "This is a notable quote."
        assert sc.quote_attribution == "Famous Person, Title"

    def test_video_slide_content(self):
        """Can create video slide content."""
        sc = SlideContent(
            slide_type=SlideType.VIDEO,
            headline="Video Title",
            video_url="https://youtube.com/watch?v=abc",
            video_caption="Watch the demo",
        )
        assert sc.slide_type == SlideType.VIDEO
        assert "youtube.com" in sc.video_url
        assert sc.video_caption == "Watch the demo"

    def test_slide_content_defaults(self):
        """SlideContent has sensible defaults."""
        sc = SlideContent(
            headline="Test",
        )
        assert sc.slide_type == SlideType.BULLETS
        assert sc.bullets == []
        assert sc.quote_text is None
        assert sc.video_url is None


# ============================================================================
# SlidesJSONGenerator Tests
# ============================================================================


class TestSlidesJSONGenerator:
    """Tests for SlidesJSONGenerator class."""

    def test_generator_creates_valid_json(self, processed_result_bullets):
        """Generator produces valid JSON string."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        output = gen.generate([processed_result_bullets])

        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)
        assert "slides" in data
        assert "generated_at" in data

    def test_generator_includes_all_slides(self, processed_result_bullets, processed_result_video):
        """Generator includes all processed results."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        output = gen.generate([processed_result_bullets, processed_result_video])

        data = json.loads(output)
        assert data["total_slides"] == 2
        assert len(data["slides"]) == 2

    def test_bullet_slide_structure(self, processed_result_bullets):
        """Bullet slide has correct structure."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        output = gen.generate([processed_result_bullets])

        data = json.loads(output)
        slide = data["slides"][0]

        assert slide["type"] == "bullets"
        assert "headline" in slide
        assert "bullets" in slide
        assert isinstance(slide["bullets"], list)
        assert "source" in slide
        assert "source_url" in slide

    def test_video_slide_detection(self, processed_result_video):
        """Video URLs are detected correctly."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        output = gen.generate([processed_result_video])

        data = json.loads(output)
        slide = data["slides"][0]

        assert slide["type"] == "video"
        assert "video_url" in slide

    def test_theme_grouping(self, processed_result_bullets):
        """Results are grouped by theme."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        output = gen.generate([processed_result_bullets])

        data = json.loads(output)
        assert "themes" in data
        assert len(data["themes"]) >= 1
        assert data["slides"][0]["theme"] in data["themes"]

    def test_aggregated_results(self, aggregated_result):
        """Aggregated results include source count."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        result_set = AggregatedResultSet(
            results=[aggregated_result],
            total_original=2,
            total_aggregated=1,
            duplicates_merged=1,
        )

        output = gen.generate_aggregated(result_set)
        data = json.loads(output)

        assert data["total_sources"] == 2
        assert data["duplicates_merged"] == 1
        slide = data["slides"][0]
        assert slide["source_count"] == 2
        assert "all_sources" in slide


# ============================================================================
# Quote Detection Consistency Tests
# ============================================================================


class TestQuoteDetectionConsistency:
    """Tests for unified quote detection logic."""

    def test_quote_min_length_constant(self):
        """QUOTE_MIN_LENGTH constant exists and is consistent."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        assert hasattr(gen, "QUOTE_MIN_LENGTH")
        assert gen.QUOTE_MIN_LENGTH == 30

    def test_short_quote_not_detected(self):
        """Quotes shorter than threshold are not detected as quote slides."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        # Create result with short quote (< 30 chars)
        result = ProcessedResult(
            url="https://example.com/article",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Test article.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
                footnotes=[
                    Footnote(id=1, source_text="Short quote", context="Person"),
                ],
            ),
        )

        assert not gen._has_quotable_content(result)

    def test_long_quote_with_context_detected(self):
        """Quotes longer than threshold with context are detected."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        # Create result with long quote (> 30 chars) with context
        result = ProcessedResult(
            url="https://example.com/article",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Test article.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
                footnotes=[
                    Footnote(
                        id=1,
                        source_text="This is a much longer quote that exceeds thirty characters easily.",
                        context="Famous Person, CEO",
                    ),
                ],
            ),
        )

        assert gen._has_quotable_content(result)

    def test_long_quote_without_context_not_detected(self):
        """Quotes without context are not detected as quote slides."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        result = ProcessedResult(
            url="https://example.com/article",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Test article.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
                footnotes=[
                    Footnote(
                        id=1,
                        source_text="This is a much longer quote that exceeds thirty characters easily.",
                        context="",  # Empty context
                    ),
                ],
            ),
        )

        assert not gen._has_quotable_content(result)


# ============================================================================
# Theme Detection Consistency Tests
# ============================================================================


class TestThemeDetectionConsistency:
    """Tests for unified theme detection logic."""

    def test_word_boundary_matching(self):
        """Theme detection uses word boundaries."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        # "AI" should match, but not as part of "CHAIR"
        result_ai = AggregatedResult(
            title="AI Model Launch",
            sources=[SourceReference(url="https://example.com", site_name="Test")],
            summary=ContentSummary(
                executive_summary="About AI.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
                topics=["AI", "Technology"],
            ),
            original_count=1,
        )

        theme = gen._detect_aggregated_theme(result_ai)
        assert theme == "AI Models & Product Launches"

    def test_theme_from_topics(self):
        """Theme detected from topics list."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        result = AggregatedResult(
            title="Industry News",
            sources=[SourceReference(url="https://example.com", site_name="Test")],
            summary=ContentSummary(
                executive_summary="News about data centers.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
                topics=["data center", "infrastructure"],
            ),
            original_count=1,
        )

        theme = gen._detect_aggregated_theme(result)
        assert theme == "AI Infrastructure & Hardware"

    def test_default_theme_fallback(self):
        """Falls back to default theme when no keywords match."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        result = AggregatedResult(
            title="Unrelated News",
            sources=[SourceReference(url="https://example.com", site_name="Test")],
            summary=ContentSummary(
                executive_summary="Something unrelated.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
                topics=["weather", "sports"],
            ),
            original_count=1,
        )

        theme = gen._detect_aggregated_theme(result)
        assert theme == "Other AI News"


# ============================================================================
# Video URL Detection Tests
# ============================================================================


class TestVideoURLDetection:
    """Tests for video URL detection."""

    def test_youtube_detection(self):
        """YouTube URLs are detected."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        result = ProcessedResult(
            url="https://youtube.com/watch?v=abc123",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Video content.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
            ),
        )

        assert gen._has_video_content(result)

    def test_vimeo_detection(self):
        """Vimeo URLs are detected."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        result = ProcessedResult(
            url="https://vimeo.com/123456",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Video content.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
            ),
        )

        assert gen._has_video_content(result)

    def test_non_video_url(self):
        """Non-video URLs are not detected as video."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()

        result = ProcessedResult(
            url="https://blog.google/article",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Article content.",
                key_points=["Point"],
                sentiment=Sentiment.NEUTRAL,
            ),
        )

        assert not gen._has_video_content(result)


# ============================================================================
# Filename Generation Tests
# ============================================================================


class TestFilenameGeneration:
    """Tests for filename generation."""

    def test_get_filename_format(self):
        """Filename has expected format."""
        from src.export.slides_json import SlidesJSONGenerator

        gen = SlidesJSONGenerator()
        filename = gen.get_filename()

        assert filename.startswith("slides_")
        assert filename.endswith(".json")
        # Should contain date in MM_DD_YY format
        parts = filename.replace("slides_", "").replace(".json", "").split("_")
        assert len(parts) == 3
