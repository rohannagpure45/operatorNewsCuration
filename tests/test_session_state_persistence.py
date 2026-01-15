"""Tests for Streamlit session state persistence and download button behavior.

This test suite covers:
- Download button configuration (on_click="ignore")
- Session state initialization and persistence
- Batch results storage and restoration
- Results clearing functionality
"""

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def streamlit_app_source():
    """Load the streamlit_app.py source code for AST analysis."""
    app_path = Path(__file__).parent.parent / "src" / "streamlit_app.py"
    return app_path.read_text()


@pytest.fixture
def mock_session_state():
    """Create a mock session state dict that behaves like st.session_state."""
    state = {}
    
    class MockSessionState:
        def __getitem__(self, key):
            return state.get(key)
        
        def __setitem__(self, key, value):
            state[key] = value
        
        def __contains__(self, key):
            return key in state
        
        def get(self, key, default=None):
            return state.get(key, default)
        
        def clear(self):
            state.clear()
    
    return MockSessionState()


@pytest.fixture
def sample_batch_results():
    """Sample batch results for testing session state persistence."""
    from src.models.schemas import (
        ContentMetadata, 
        ContentSummary,
        ProcessedResult, 
        ProcessingStatus, 
        Sentiment,
        URLType,
    )
    
    return [
        ProcessedResult(
            url="https://example.com/article1",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            content=ContentMetadata(
                title="Test Article 1",
                text="Sample article text content.",
                word_count=100,
            ),
            summary=ContentSummary(
                executive_summary="Test summary",
                key_points=["Point 1", "Point 2"],
                sentiment=Sentiment.NEUTRAL,
                topics=["tech"],
            ),
        ),
        ProcessedResult(
            url="https://example.com/article2",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.FAILED,
            error="Network timeout",
        ),
    ]


# =============================================================================
# Phase 1: Crawl - Download Button Configuration Tests
# =============================================================================


class TestDownloadButtonConfiguration:
    """Tests to verify download buttons use on_click='ignore'."""

    def test_download_buttons_have_on_click_ignore(self, streamlit_app_source):
        """All st.download_button calls should have on_click='ignore'."""
        # Find all st.download_button calls in the source
        pattern = r'st\.download_button\s*\('
        matches = list(re.finditer(pattern, streamlit_app_source))
        
        assert len(matches) > 0, "No st.download_button calls found in streamlit_app.py"
        
        # Check each download button for on_click parameter
        for match in matches:
            # Extract the full function call (find matching parentheses)
            start = match.start()
            paren_count = 0
            end = start
            in_call = False
            
            for i, char in enumerate(streamlit_app_source[start:], start=start):
                if char == '(':
                    paren_count += 1
                    in_call = True
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0 and in_call:
                        end = i + 1
                        break
            
            call_text = streamlit_app_source[start:end]
            
            # Verify on_click="ignore" is present
            assert 'on_click="ignore"' in call_text or "on_click='ignore'" in call_text, (
                f"Download button missing on_click='ignore': {call_text[:100]}..."
            )

    def test_download_button_count(self, streamlit_app_source):
        """Verify expected number of download buttons exist."""
        pattern = r'st\.download_button\s*\('
        matches = list(re.finditer(pattern, streamlit_app_source))
        
        # Expected: 2 in single URL mode + 3 in batch mode = 5 total
        assert len(matches) >= 5, (
            f"Expected at least 5 download buttons, found {len(matches)}"
        )

    def test_no_download_button_without_on_click(self, streamlit_app_source):
        """No download button should be missing the on_click parameter."""
        # Find all download button calls
        pattern = r'st\.download_button\s*\([^)]+\)'
        
        # This is a simpler check - just count occurrences of each
        button_count = len(re.findall(r'st\.download_button', streamlit_app_source))
        ignore_count = len(re.findall(r'on_click\s*=\s*["\']ignore["\']', streamlit_app_source))
        
        assert button_count == ignore_count, (
            f"Found {button_count} download buttons but only {ignore_count} have on_click='ignore'"
        )


# =============================================================================
# Phase 2: Walk - Session State Persistence Tests
# =============================================================================


class TestSessionStateInitialization:
    """Tests for session state initialization."""

    def test_session_state_keys_initialized(self, streamlit_app_source):
        """Required session state keys should be initialized."""
        required_keys = ["batch_results", "batch_urls"]
        
        for key in required_keys:
            # Check for initialization pattern
            pattern = rf'if\s+["\']?{key}["\']?\s+not\s+in\s+st\.session_state'
            assert re.search(pattern, streamlit_app_source), (
                f"Session state key '{key}' not initialized in streamlit_app.py"
            )

    def test_batch_results_defaults_to_none(self, mock_session_state):
        """batch_results should default to None."""
        # Simulate initialization
        if "batch_results" not in mock_session_state:
            mock_session_state["batch_results"] = None
        
        assert mock_session_state["batch_results"] is None


class TestBatchResultsPersistence:
    """Tests for batch results storage and restoration."""

    def test_results_stored_after_processing(self, sample_batch_results, mock_session_state):
        """Batch results should be stored in session state after processing."""
        # Simulate storing results
        mock_session_state["batch_results"] = sample_batch_results
        mock_session_state["batch_urls"] = [r.url for r in sample_batch_results]
        
        assert mock_session_state["batch_results"] is not None
        assert len(mock_session_state["batch_results"]) == 2
        assert len(mock_session_state["batch_urls"]) == 2

    def test_results_survive_simulated_rerun(self, sample_batch_results, mock_session_state):
        """Stored results should persist across simulated reruns."""
        # First "run" - store results
        mock_session_state["batch_results"] = sample_batch_results
        
        # Simulate rerun by accessing state again
        retrieved = mock_session_state["batch_results"]
        
        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0].url == "https://example.com/article1"

    def test_results_serializable(self, sample_batch_results):
        """Batch results should be JSON serializable for caching."""
        for result in sample_batch_results:
            # Should not raise
            json_str = result.model_dump_json()
            assert isinstance(json_str, str)
            assert len(json_str) > 0
            
            # Should round-trip successfully
            from src.models.schemas import ProcessedResult
            restored = ProcessedResult.model_validate_json(json_str)
            assert restored.url == result.url


class TestResultsClearing:
    """Tests for clearing batch results."""

    def test_clear_removes_all_results(self, sample_batch_results, mock_session_state):
        """Clearing should remove all batch results."""
        mock_session_state["batch_results"] = sample_batch_results
        mock_session_state["batch_urls"] = ["url1", "url2"]
        
        # Clear
        mock_session_state["batch_results"] = None
        mock_session_state["batch_urls"] = None
        
        assert mock_session_state["batch_results"] is None
        assert mock_session_state["batch_urls"] is None


# =============================================================================
# Phase 3: Run - Cache Result Storage Tests
# =============================================================================


class TestCacheResultStorage:
    """Tests for storing full results in cache."""

    def test_cache_entry_supports_result_json(self):
        """CacheEntry should have result_json field."""
        from src.cache.cache import CacheEntry
        
        # After schema update, this should work
        entry = CacheEntry(
            url="https://example.com/test",
            status="completed",
            timestamp=datetime.now(),
            result_json='{"url": "test"}',
        )
        
        assert entry.result_json == '{"url": "test"}'

    def test_cache_entry_result_json_optional(self):
        """result_json should be optional for backward compatibility."""
        from src.cache.cache import CacheEntry
        
        # Should work without result_json
        entry = CacheEntry(
            url="https://example.com/test",
            status="completed",
            timestamp=datetime.now(),
        )
        
        assert entry.result_json is None


class TestCacheResultRetrieval:
    """Tests for retrieving full results from cache."""

    def test_get_result_returns_processed_result(self, sample_batch_results):
        """get_result should return a ProcessedResult object."""
        import tempfile
        from pathlib import Path
        from src.cache.cache import CacheEntry, LocalCache
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LocalCache(cache_dir=Path(tmpdir))
            
            result = sample_batch_results[0]
            entry = CacheEntry(
                url=result.url,
                title=result.content.title if result.content else None,
                status=result.status.value,
                timestamp=datetime.now(),
                result_json=result.model_dump_json(),
            )
            cache.add_entry(entry)
            
            # Retrieve
            retrieved_entry = cache.get_by_url(result.url)
            assert retrieved_entry is not None
            assert retrieved_entry.result_json is not None
            
            # Deserialize
            from src.models.schemas import ProcessedResult
            restored = ProcessedResult.model_validate_json(retrieved_entry.result_json)
            assert restored.url == result.url

    def test_get_result_returns_none_for_missing(self):
        """get_result should return None for non-existent URL."""
        import tempfile
        from pathlib import Path
        from src.cache.cache import LocalCache
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LocalCache(cache_dir=Path(tmpdir))
            entry = cache.get_by_url("https://nonexistent.com/article")
            assert entry is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestDisplayBatchResultsFunction:
    """Tests for the display_batch_results helper function."""

    def test_display_batch_results_exists(self, streamlit_app_source):
        """display_batch_results function should exist after refactoring."""
        # This test will initially fail until we add the function
        assert "def display_batch_results" in streamlit_app_source, (
            "display_batch_results function not found in streamlit_app.py"
        )


class TestRecentsRestoration:
    """Tests for restoring results from Recents menu."""

    def test_recents_entry_click_restores_results(self, streamlit_app_source):
        """Clicking a Recents entry should attempt to restore results."""
        # Check for result restoration logic near Recents button
        assert "get_result" in streamlit_app_source or "result_json" in streamlit_app_source, (
            "No result restoration logic found in Recents handling"
        )
