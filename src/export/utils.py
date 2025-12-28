"""Shared utilities for export generators.

Contains common theme detection, sentiment colors, and text sanitization
used across PDFReportGenerator, PrepDocumentGenerator, and SlidesDeckGenerator.
"""

import re
from typing import Dict, List, Tuple

from src.models.schemas import ClaimRating, ProcessedResult, Sentiment


# Theme keywords for grouping articles by topic
THEME_KEYWORDS: Dict[str, List[str]] = {
    "AI Models & Product Launches": [
        "gpt", "gemini", "llm", "model", "release", "launch", "codex", "claude"
    ],
    "AI Infrastructure & Hardware": [
        "data center", "gpu", "nvidia", "ssd", "memory", "hardware", "chip", "hynix"
    ],
    "AI M&A and Funding": [
        "acquire", "acquisition", "funding", "investment", "billion", "deal", "raise", "groq"
    ],
    "AI Research & Competitions": [
        "research", "benchmark", "arc prize", "competition", "lab", "scientific"
    ],
    "AI Workforce & Industry": [
        "layoff", "job", "workforce", "industry", "enterprise", "hiring"
    ],
}

# Default theme when no keywords match
DEFAULT_THEME = "Other AI Developments"

# Sentiment color mappings (RGB tuples for PDF rendering)
SENTIMENT_COLORS: Dict[Sentiment, Tuple[int, int, int]] = {
    Sentiment.POSITIVE: (34, 197, 94),     # Green
    Sentiment.NEGATIVE: (239, 68, 68),     # Red
    Sentiment.NEUTRAL: (107, 114, 128),    # Gray
    Sentiment.MIXED: (245, 158, 11),       # Orange/Amber
}

# Sentiment display labels
SENTIMENT_LABELS: Dict[Sentiment, str] = {
    Sentiment.POSITIVE: "Positive",
    Sentiment.NEGATIVE: "Negative",
    Sentiment.NEUTRAL: "Neutral",
    Sentiment.MIXED: "Mixed",
}

# Fact-check rating color mappings (RGB tuples)
RATING_COLORS: Dict[ClaimRating, Tuple[int, int, int]] = {
    ClaimRating.TRUE: (34, 197, 94),
    ClaimRating.MOSTLY_TRUE: (132, 204, 22),
    ClaimRating.MIXED: (245, 158, 11),
    ClaimRating.MOSTLY_FALSE: (249, 115, 22),
    ClaimRating.FALSE: (239, 68, 68),
    ClaimRating.UNVERIFIED: (107, 114, 128),
    ClaimRating.INSUFFICIENT_DATA: (107, 114, 128),
}

# Entity type colors for PDF rendering (RGB tuples)
ENTITY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "PERSON": (219, 234, 254),    # Light blue
    "ORG": (243, 232, 255),       # Light purple
    "LOC": (220, 252, 231),       # Light green
    "DATE": (254, 243, 199),      # Light yellow
    "MONEY": (209, 250, 229),     # Light teal
    "PRODUCT": (252, 231, 243),   # Light pink
    "EVENT": (254, 226, 226),     # Light red
}


def sanitize_text(obj):
    """
    Recursively replace unicode chars that fpdf can't handle.
    
    Args:
        obj: String, dict, list, or other object to sanitize.
        
    Returns:
        Sanitized object with problematic unicode characters replaced.
    """
    if isinstance(obj, str):
        # Replace em-dash, en-dash, smart quotes, bullets
        obj = obj.replace('\u2014', '-').replace('\u2013', '-')
        obj = obj.replace('\u2018', "'").replace('\u2019', "'")
        obj = obj.replace('\u201c', '"').replace('\u201d', '"')
        obj = obj.replace('\u2022', '*').replace('\u2026', '...')
        obj = obj.replace('\u2011', '-')  # Non-breaking hyphen
        obj = obj.replace('\u00a0', ' ')  # Non-breaking space
        obj = obj.replace('\u2003', ' ')  # Em space
        obj = obj.replace('\u2002', ' ')  # En space
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_text(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_text(x) for x in obj]
    return obj


def detect_theme(
    result: ProcessedResult,
    use_word_boundaries: bool = False,
    default_theme: str = DEFAULT_THEME,
) -> str:
    """
    Detect the theme of an article based on content.
    
    Args:
        result: ProcessedResult to analyze.
        use_word_boundaries: If True, use regex word boundaries for matching.
                            If False, use simple substring matching.
        default_theme: Theme to return when no keywords match.
                      Defaults to DEFAULT_THEME ("Other AI Developments").
    
    Returns:
        Theme string from THEME_KEYWORDS keys, or default_theme if no match.
    """
    # Combine title, topics, and summary for keyword matching
    text_parts = []
    if result.content and result.content.title:
        text_parts.append(result.content.title.lower())
    if result.summary:
        if result.summary.topics:
            text_parts.extend([t.lower() for t in result.summary.topics])
        if result.summary.executive_summary:
            text_parts.append(result.summary.executive_summary.lower())
    
    combined_text = " ".join(text_parts)
    
    for theme, keywords in THEME_KEYWORDS.items():
        if use_word_boundaries:
            # Use regex word boundaries to avoid false positives
            if any(re.search(r'\b' + re.escape(kw) + r'\b', combined_text) for kw in keywords):
                return theme
        else:
            # Simple substring matching
            if any(kw in combined_text for kw in keywords):
                return theme
    
    return default_theme

