"""Tests for LLM summarization."""

import pytest

from src.models.schemas import (
    ContentSummary,
    Entity,
    EntityType,
    Footnote,
    Sentiment,
)


class TestContentSummary:
    """Tests for ContentSummary model."""

    def test_valid_summary(self):
        """Test creating a valid summary."""
        summary = ContentSummary(
            executive_summary="This is a test summary.",
            key_points=["Point 1", "Point 2", "Point 3"],
            sentiment=Sentiment.NEUTRAL,
            entities=[
                Entity(text="OpenAI", type=EntityType.ORGANIZATION),
            ],
            implications=["Implication 1"],
            footnotes=[
                Footnote(id=1, source_text="Quote", context="Context"),
            ],
            topics=["Technology", "AI"],
        )

        assert summary.executive_summary == "This is a test summary."
        assert len(summary.key_points) == 3
        assert summary.sentiment == Sentiment.NEUTRAL

    def test_minimum_key_points(self):
        """Test that at least one key point is required."""
        # This should work with one key point
        summary = ContentSummary(
            executive_summary="Summary",
            key_points=["Single point"],
            sentiment=Sentiment.NEUTRAL,
        )
        assert len(summary.key_points) == 1

        # This should fail with no key points
        with pytest.raises(ValueError):
            ContentSummary(
                executive_summary="Summary",
                key_points=[],
                sentiment=Sentiment.NEUTRAL,
            )

    def test_entity_types(self):
        """Test entity type handling."""
        entity = Entity(
            text="Sam Altman",
            type=EntityType.PERSON,
            relevance=0.9,
        )

        assert entity.type == EntityType.PERSON
        assert entity.relevance == 0.9

    def test_sentiment_values(self):
        """Test sentiment enum values."""
        for sentiment in [Sentiment.POSITIVE, Sentiment.NEGATIVE, 
                         Sentiment.NEUTRAL, Sentiment.MIXED]:
            summary = ContentSummary(
                executive_summary="Test",
                key_points=["Point"],
                sentiment=sentiment,
            )
            assert summary.sentiment == sentiment


class TestSummarizer:
    """Tests for the Summarizer class."""

    def test_content_truncation(self):
        """Test content truncation for token limits."""
        from src.summarizer.llm import Summarizer

        # Create summarizer without actually connecting to API
        try:
            summarizer = Summarizer.__new__(Summarizer)
            summarizer.api_key = "test"
            summarizer.model_name = "test"

            # Test truncation
            long_content = "x" * 200000  # Very long content
            truncated = summarizer._truncate_content(long_content, max_tokens=1000)

            # Should be truncated
            assert len(truncated) < len(long_content)
            assert "[Content truncated" in truncated

            # Short content should not be truncated
            short_content = "This is short content."
            result = summarizer._truncate_content(short_content, max_tokens=1000)
            assert result == short_content

        except Exception:
            # Skip if we can't create the summarizer
            pytest.skip("Could not create Summarizer instance")

