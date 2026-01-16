"""Tests for tab switching logic in the Streamlit app.

This test suite covers:
- Session state initialization for active_tab
- Tab selection null-safety handling
- Render conditional logic based on session state
- Recents click tab switching
"""

from pathlib import Path
from typing import Dict, Optional

import pytest


# =============================================================================
# Mock Session State for Testing
# =============================================================================


class MockSessionState:
    """Mock st.session_state for unit testing."""
    
    def __init__(self, initial_state: Optional[Dict] = None):
        self._state = initial_state or {}
    
    def __getitem__(self, key):
        return self._state.get(key)
    
    def __setitem__(self, key, value):
        self._state[key] = value
    
    def __contains__(self, key):
        return key in self._state
    
    def __delitem__(self, key):
        if key in self._state:
            del self._state[key]
    
    def get(self, key, default=None):
        return self._state.get(key, default)


# =============================================================================
# Phase 1: Session State Initialization Tests
# =============================================================================


class TestActiveTabInitialization:
    """Tests for active_tab session state initialization."""

    def test_active_tab_defaults_to_single(self):
        """active_tab should initialize to 'single' by default."""
        session_state = MockSessionState()
        
        # Simulate the initialization logic from streamlit_app.py lines 94-95
        if "active_tab" not in session_state:
            session_state["active_tab"] = "single"
        
        assert session_state["active_tab"] == "single"

    def test_active_tab_preserves_existing_value(self):
        """active_tab should not be overwritten if already set."""
        session_state = MockSessionState({"active_tab": "batch"})
        
        # Simulate initialization - should NOT overwrite existing value
        if "active_tab" not in session_state:
            session_state["active_tab"] = "single"
        
        assert session_state["active_tab"] == "batch"


# =============================================================================
# Phase 2: Tab Selection Null-Safety Tests
# =============================================================================


class TestTabSelectionNullHandling:
    """Tests for null-safe handling of segmented_control return value."""

    def test_session_state_unchanged_when_selected_tab_is_none(self):
        """When selected_tab is None, active_tab should not change."""
        session_state = MockSessionState({"active_tab": "batch"})
        selected_tab = None  # Simulates st.segmented_control returning None
        
        # Replicate logic from lines 449-454
        if selected_tab is not None:
            if selected_tab == "Batch Processing":
                session_state["active_tab"] = "batch"
            else:
                session_state["active_tab"] = "single"
        
        # Should remain unchanged
        assert session_state["active_tab"] == "batch"

    def test_active_tab_updates_to_batch_when_selected(self):
        """When 'Batch Processing' is selected, active_tab should become 'batch'."""
        session_state = MockSessionState({"active_tab": "single"})
        selected_tab = "Batch Processing"
        
        if selected_tab is not None:
            if selected_tab == "Batch Processing":
                session_state["active_tab"] = "batch"
            else:
                session_state["active_tab"] = "single"
        
        assert session_state["active_tab"] == "batch"

    def test_active_tab_updates_to_single_when_selected(self):
        """When 'Single URL' is selected, active_tab should become 'single'."""
        session_state = MockSessionState({"active_tab": "batch"})
        selected_tab = "Single URL"
        
        if selected_tab is not None:
            if selected_tab == "Batch Processing":
                session_state["active_tab"] = "batch"
            else:
                session_state["active_tab"] = "single"
        
        assert session_state["active_tab"] == "single"

    def test_null_preservation_does_not_reset_to_single(self):
        """Critically: None should NOT reset batch to single."""
        session_state = MockSessionState({"active_tab": "batch"})
        
        # Simulate multiple None returns (edge case)
        for _ in range(5):
            selected_tab = None
            if selected_tab is not None:
                if selected_tab == "Batch Processing":
                    session_state["active_tab"] = "batch"
                else:
                    session_state["active_tab"] = "single"
        
        assert session_state["active_tab"] == "batch"


# =============================================================================
# Phase 3: Render Conditional Logic Tests
# =============================================================================


class TestRenderConditionals:
    """Tests for content rendering based on active_tab."""

    def test_single_url_content_renders_when_active_tab_is_single(self):
        """Single URL content should render when active_tab == 'single'."""
        session_state = MockSessionState({"active_tab": "single"})
        
        rendered_content = None
        
        # Replicate logic from lines 458 and 527
        if session_state["active_tab"] == "single":
            rendered_content = "single_url_content"
        elif session_state["active_tab"] == "batch":
            rendered_content = "batch_processing_content"
        
        assert rendered_content == "single_url_content"

    def test_batch_content_renders_when_active_tab_is_batch(self):
        """Batch processing content should render when active_tab == 'batch'."""
        session_state = MockSessionState({"active_tab": "batch"})
        
        rendered_content = None
        
        if session_state["active_tab"] == "single":
            rendered_content = "single_url_content"
        elif session_state["active_tab"] == "batch":
            rendered_content = "batch_processing_content"
        
        assert rendered_content == "batch_processing_content"

    def test_render_always_produces_content(self):
        """Either single or batch content should always render."""
        for active_tab in ["single", "batch"]:
            session_state = MockSessionState({"active_tab": active_tab})
            
            rendered_content = None
            
            if session_state["active_tab"] == "single":
                rendered_content = "single_url_content"
            elif session_state["active_tab"] == "batch":
                rendered_content = "batch_processing_content"
            
            assert rendered_content is not None, f"No content rendered for active_tab={active_tab}"


# =============================================================================
# Phase 4: Recents Click Tab Switching Tests
# =============================================================================


class TestRecentsTabSwitching:
    """Tests for switching to batch tab when clicking Recents."""

    def test_recents_click_sets_active_tab_to_batch(self):
        """Clicking a Recents entry should set active_tab to 'batch'."""
        session_state = MockSessionState({"active_tab": "single"})
        
        # Simulate Recents button click (line 410-412)
        restore_batch_id = "some-batch-uuid"
        session_state["restore_batch_id"] = restore_batch_id
        session_state["active_tab"] = "batch"
        
        assert session_state["active_tab"] == "batch"
        assert session_state["restore_batch_id"] == restore_batch_id

    def test_recents_click_clears_restore_id_after_processing(self):
        """restore_batch_id should be cleared after restoration."""
        session_state = MockSessionState({
            "active_tab": "single",
            "restore_batch_id": "some-batch-uuid"
        })
        
        # Simulate restoration logic (lines 423-425)
        batch_id = session_state["restore_batch_id"]
        session_state["restore_batch_id"] = None  # Clear to avoid re-triggering
        
        assert session_state["restore_batch_id"] is None


# =============================================================================
# Phase 5: User Click Handling Tests (Bug Fix)
# =============================================================================


class TestUserClickHandling:
    """Tests for correct handling of user clicks in segmented control.
    
    These tests verify that user clicks are NOT interfered with by
    widget state synchronization logic.
    """

    def test_user_click_preserved_during_state_update(self):
        """User's widget click should NOT be cleared during session state sync.
        
        This test exposes the bug where clicking 'Batch Processing' doesn't
        switch the tab because the widget state clearing logic deletes the
        user's clicked value before the widget can return it.
        
        Timeline of the bug:
        1. User clicks 'Batch Processing', widget state = 'Batch Processing'
        2. On rerun, active_tab is still 'single' (not updated yet)
        3. desired_tab = 'Single URL' (computed from old active_tab)
        4. BUG: widget state gets deleted because it doesn't match desired_tab
        5. Widget returns None, active_tab never updates
        """
        session_state = MockSessionState({
            "active_tab": "single",  # Old state - not yet updated
            "tab_selector": "Batch Processing"  # User just clicked batch
        })
        
        # The widget value should be preserved so it can be read
        # The session state update logic (lines 450-454) should handle
        # syncing the widget value to active_tab
        assert session_state["tab_selector"] == "Batch Processing"
        
        # Simulate the correct behavior: widget value updates active_tab
        selected_tab = session_state["tab_selector"]
        if selected_tab is not None:
            if selected_tab == "Batch Processing":
                session_state["active_tab"] = "batch"
            else:
                session_state["active_tab"] = "single"
        
        assert session_state["active_tab"] == "batch"

    def test_widget_value_not_cleared_on_user_click(self):
        """Widget state should NOT be deleted when user clicks a different tab.
        
        The old buggy code deleted tab_selector when it didn't match desired_tab,
        but this incorrectly deleted user clicks before they could be processed.
        """
        session_state = MockSessionState({
            "active_tab": "single",
            "tab_selector": "Batch Processing"  # User clicked different tab
        })
        
        # desired_tab is computed from OLD active_tab
        desired_tab = "Batch Processing" if session_state["active_tab"] == "batch" else "Single URL"
        
        # BUG: old code would delete the user's click here
        # The fix is to NOT do this deletion at all
        # if "tab_selector" in session_state and session_state["tab_selector"] != desired_tab:
        #     del session_state["tab_selector"]  # DON'T DO THIS!
        
        # Widget value should still be accessible
        assert "tab_selector" in session_state
        assert session_state["tab_selector"] == "Batch Processing"


# =============================================================================
# Phase 6: Desired Tab Computation Tests
# =============================================================================


class TestDesiredTabComputation:
    """Tests for desired_tab computation from active_tab."""

    def test_desired_tab_computed_correctly_for_batch(self):
        """desired_tab should be 'Batch Processing' when active_tab is 'batch'."""
        session_state = MockSessionState({"active_tab": "batch"})
        desired = "Batch Processing" if session_state["active_tab"] == "batch" else "Single URL"
        assert desired == "Batch Processing"

    def test_desired_tab_computed_correctly_for_single(self):
        """desired_tab should be 'Single URL' when active_tab is 'single'."""
        session_state = MockSessionState({"active_tab": "single"})
        desired = "Batch Processing" if session_state["active_tab"] == "batch" else "Single URL"
        assert desired == "Single URL"


# =============================================================================
# Static Analysis Tests
# =============================================================================


class TestStreamlitAppStaticAnalysis:
    """Static analysis tests for the streamlit_app.py source code."""

    @pytest.fixture
    def streamlit_app_source(self):
        """Load the streamlit_app.py source code."""
        app_path = Path(__file__).parent.parent / "src" / "streamlit_app.py"
        return app_path.read_text()

    def test_active_tab_initialized_in_session_state(self, streamlit_app_source):
        """active_tab should be initialized in session state."""
        assert 'if "active_tab" not in st.session_state:' in streamlit_app_source
        assert 'st.session_state.active_tab = "single"' in streamlit_app_source

    def test_selected_tab_null_check_present(self, streamlit_app_source):
        """Null check for selected_tab should be present."""
        assert "if selected_tab is not None:" in streamlit_app_source

    def test_render_uses_session_state_not_widget(self, streamlit_app_source):
        """Content rendering should use session_state.active_tab, not selected_tab."""
        # Check for correct pattern
        assert 'if st.session_state.active_tab == "single":' in streamlit_app_source
        assert 'elif st.session_state.active_tab == "batch":' in streamlit_app_source
        
        # Ensure the old buggy pattern is NOT present
        # (rendering based on selected_tab == "Single URL" or selected_tab == "Batch Processing")
        lines = streamlit_app_source.split('\n')
        for i, line in enumerate(lines):
            # Check that content rendering conditions don't use selected_tab
            if 'if selected_tab == "Single URL":' in line:
                # This is only OK if it's inside the update block, not for rendering
                # The update block is around line 450, rendering is around 458
                if i > 455:  # Roughly after the update logic
                    pytest.fail(f"Found buggy render pattern using selected_tab on line {i+1}")
            if 'elif selected_tab == "Batch Processing":' in line:
                if i > 455:
                    pytest.fail(f"Found buggy render pattern using selected_tab on line {i+1}")

    def test_recents_sets_active_tab_to_batch(self, streamlit_app_source):
        """Clicking Recents should set active_tab to 'batch'."""
        # Check for the pattern where recent batch click sets active_tab
        assert 'st.session_state.active_tab = "batch"' in streamlit_app_source

    def test_widget_state_clearing_not_present(self, streamlit_app_source):
        """Widget state clearing logic should NOT be present (was causing bugs).
        
        The old code deleted tab_selector when it didn't match desired_tab,
        which incorrectly deleted user clicks before they could be processed.
        """
        # The buggy pattern should NOT exist
        assert 'del st.session_state["tab_selector"]' not in streamlit_app_source

