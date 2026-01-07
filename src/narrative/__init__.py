"""Narrative Theme System module.

Provides configurable narrative framing for content summarization.
"""

from src.narrative.themes import NarrativeTheme, get_theme_from_string
from src.narrative.engine import NarrativeFramingEngine

__all__ = [
    "NarrativeTheme",
    "NarrativeFramingEngine",
    "get_theme_from_string",
]
