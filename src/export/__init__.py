"""Export module for generating PDF reports and other export formats."""

from src.export.pdf_report import PDFReportGenerator
from src.export.prep_document import PrepDocumentGenerator
from src.export.slides_deck import SlidesDeckGenerator
from src.export.slides_json import SlidesJSONGenerator
from src.export.utils import (
    DEFAULT_THEME,
    ENTITY_COLORS,
    RATING_COLORS,
    SENTIMENT_COLORS,
    SENTIMENT_LABELS,
    THEME_KEYWORDS,
    detect_theme,
    sanitize_text,
)

__all__ = [
    # Generators
    "PDFReportGenerator",
    "PrepDocumentGenerator",
    "SlidesDeckGenerator",
    "SlidesJSONGenerator",
    # Shared utilities
    "THEME_KEYWORDS",
    "DEFAULT_THEME",
    "SENTIMENT_COLORS",
    "SENTIMENT_LABELS",
    "RATING_COLORS",
    "ENTITY_COLORS",
    "sanitize_text",
    "detect_theme",
]

