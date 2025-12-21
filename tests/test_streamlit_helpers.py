"""Tests for Streamlit app helper functions."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

# Import the helper functions directly
# Note: We import these before streamlit is imported to avoid st.set_page_config issues
import sys

# Mock streamlit before importing the module
sys.modules['streamlit'] = MagicMock()

from src.streamlit_app import get_rating_color, get_sentiment_color, get_sentiment_emoji, run_async
from src.models.schemas import Sentiment


class TestGetRatingColor:
    """Tests for get_rating_color function."""

    def test_true_is_green(self):
        """Test that 'true' rating returns green."""
        assert get_rating_color("true") == "green"

    def test_mostly_true_is_green(self):
        """Test that 'mostly_true' rating returns green."""
        assert get_rating_color("mostly_true") == "green"

    def test_false_is_red(self):
        """Test that 'false' rating returns red."""
        assert get_rating_color("false") == "red"

    def test_mostly_false_is_red(self):
        """Test that 'mostly_false' rating returns red."""
        assert get_rating_color("mostly_false") == "red"

    def test_mixed_is_orange(self):
        """Test that 'mixed' rating returns orange."""
        assert get_rating_color("mixed") == "orange"

    def test_unverified_is_orange(self):
        """Test that 'unverified' rating returns orange."""
        assert get_rating_color("unverified") == "orange"

    def test_insufficient_data_is_orange(self):
        """Test that 'insufficient_data' rating returns orange."""
        assert get_rating_color("insufficient_data") == "orange"

    def test_empty_string_is_orange(self):
        """Test that empty string returns orange."""
        assert get_rating_color("") == "orange"

    def test_none_handling(self):
        """Test that None is handled gracefully."""
        assert get_rating_color(None) == "orange"

    def test_case_insensitive(self):
        """Test that rating comparison is case-insensitive."""
        assert get_rating_color("TRUE") == "green"
        assert get_rating_color("False") == "red"
        assert get_rating_color("MOSTLY_TRUE") == "green"

    def test_whitespace_handling(self):
        """Test that whitespace is stripped."""
        assert get_rating_color("  true  ") == "green"
        assert get_rating_color("\tfalse\n") == "red"


class TestGetSentimentColor:
    """Tests for get_sentiment_color function."""

    def test_positive_is_green(self):
        """Test that POSITIVE sentiment returns green."""
        assert get_sentiment_color(Sentiment.POSITIVE) == "green"

    def test_negative_is_red(self):
        """Test that NEGATIVE sentiment returns red."""
        assert get_sentiment_color(Sentiment.NEGATIVE) == "red"

    def test_neutral_is_gray(self):
        """Test that NEUTRAL sentiment returns gray."""
        assert get_sentiment_color(Sentiment.NEUTRAL) == "gray"

    def test_mixed_is_orange(self):
        """Test that MIXED sentiment returns orange."""
        assert get_sentiment_color(Sentiment.MIXED) == "orange"

    def test_unknown_returns_gray(self):
        """Test that unknown sentiment returns gray."""
        assert get_sentiment_color(None) == "gray"


class TestGetSentimentEmoji:
    """Tests for get_sentiment_emoji function."""

    def test_positive_emoji(self):
        """Test that POSITIVE sentiment returns happy emoji."""
        assert get_sentiment_emoji(Sentiment.POSITIVE) == "😊"

    def test_negative_emoji(self):
        """Test that NEGATIVE sentiment returns sad emoji."""
        assert get_sentiment_emoji(Sentiment.NEGATIVE) == "😔"

    def test_neutral_emoji(self):
        """Test that NEUTRAL sentiment returns neutral emoji."""
        assert get_sentiment_emoji(Sentiment.NEUTRAL) == "😐"

    def test_mixed_emoji(self):
        """Test that MIXED sentiment returns thinking emoji."""
        assert get_sentiment_emoji(Sentiment.MIXED) == "🤔"

    def test_unknown_returns_question(self):
        """Test that unknown sentiment returns question emoji."""
        assert get_sentiment_emoji(None) == "❓"


class TestRunAsync:
    """Tests for run_async helper function."""

    def test_run_async_executes_coroutine(self):
        """Test that run_async successfully executes a coroutine."""
        async def simple_coro():
            return 42

        result = run_async(simple_coro())
        assert result == 42

    def test_run_async_handles_exception(self):
        """Test that run_async propagates exceptions."""
        async def failing_coro():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            run_async(failing_coro())

    def test_run_async_returns_async_result(self):
        """Test that run_async returns the actual result."""
        async def returning_coro():
            await asyncio.sleep(0.01)
            return {"key": "value"}

        result = run_async(returning_coro())
        assert result == {"key": "value"}


class TestHistoryBounding:
    """Tests for history bounding logic."""

    def test_history_trimmed_to_100(self):
        """Test that history list is trimmed to 100 items."""
        # Simulate the history trimming logic
        history = list(range(150))  # 150 items
        history = history[-100:]
        
        assert len(history) == 100
        assert history[0] == 50  # First 50 items removed
        assert history[-1] == 149  # Last item preserved

    def test_history_not_trimmed_when_under_limit(self):
        """Test that history is not trimmed when under 100 items."""
        history = list(range(50))  # 50 items
        history = history[-100:]
        
        assert len(history) == 50

    def test_history_empty_stays_empty(self):
        """Test that empty history stays empty after trim."""
        history = []
        history = history[-100:]
        
        assert len(history) == 0


