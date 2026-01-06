"""Slides JSON Generator - Creates structured JSON for Figma import.

Generates JSON output optimized for importing into Figma or other design tools,
with slide type detection and short, punchy copy for presentations.
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.export.utils import detect_theme, THEME_KEYWORDS
from src.models.schemas import (
    AggregatedResult,
    AggregatedResultSet,
    ProcessedResult,
    ProcessingStatus,
    SlideType,
)


class SlidesJSONGenerator:
    """
    Generate structured JSON for slide content, optimized for Figma import.
    
    Supports three slide types:
    - bullets: Standard bullet point slides with key facts
    - quote: Featured quote slides with attribution
    - video: Video reference slides with captions
    """

    # Video URL patterns for detection
    VIDEO_PATTERNS = [
        r'youtube\.com/watch',
        r'youtu\.be/',
        r'vimeo\.com/',
        r'twitter\.com/.*/video',
        r'x\.com/.*/video',
    ]
    
    # Minimum quote length for quote slide detection (requires context/attribution)
    QUOTE_MIN_LENGTH = 30

    def __init__(self):
        """Initialize the JSON slides generator."""
        self._video_regex = re.compile('|'.join(self.VIDEO_PATTERNS), re.IGNORECASE)

    def generate(self, results: List[ProcessedResult]) -> str:
        """
        Generate JSON slides output from processed results.

        Args:
            results: List of processed results to include.

        Returns:
            JSON string with slide structure.
        """
        successful = [r for r in results if r.status == ProcessingStatus.COMPLETED and r.summary]
        grouped = self._group_by_theme(successful)
        
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_slides": len(successful),
            "themes": list(grouped.keys()),
            "slides": []
        }
        
        for theme, articles in grouped.items():
            for article in articles:
                slide = self._build_slide(article, theme)
                output["slides"].append(slide)
        
        return json.dumps(output, indent=2, ensure_ascii=False)

    def generate_aggregated(self, result_set: AggregatedResultSet) -> str:
        """
        Generate JSON slides output from aggregated results.

        Args:
            result_set: AggregatedResultSet with merged/deduplicated results.

        Returns:
            JSON string with slide structure.
        """
        successful = [r for r in result_set.results if r.status == ProcessingStatus.COMPLETED and r.summary]
        grouped = self._group_aggregated_by_theme(successful)
        
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_slides": len(successful),
            "total_sources": result_set.total_original,
            "duplicates_merged": result_set.duplicates_merged,
            "themes": list(grouped.keys()),
            "slides": []
        }
        
        for theme, articles in grouped.items():
            for article in articles:
                slide = self._build_aggregated_slide(article, theme)
                output["slides"].append(slide)
        
        return json.dumps(output, indent=2, ensure_ascii=False)

    def _build_slide(self, result: ProcessedResult, theme: str) -> Dict[str, Any]:
        """Build a single slide from a ProcessedResult."""
        # Determine slide type
        slide_type = self._detect_slide_type(result)
        
        # Get source info
        source_name = self._get_source_name(result)
        source_url = result.url or ""
        
        # Base slide structure
        slide: Dict[str, Any] = {
            "type": slide_type.value,
            "theme": theme,
            "source": source_name,
            "source_url": source_url,
        }
        
        # Use LLM-generated slide content if available
        if result.summary and result.summary.slide_content:
            sc = result.summary.slide_content
            slide["headline"] = sc.headline
            
            if slide_type == SlideType.BULLETS:
                slide["bullets"] = sc.bullets[:5] if sc.bullets else self._generate_fallback_bullets(result)
            elif slide_type == SlideType.QUOTE:
                slide["quote_text"] = sc.quote_text or ""
                slide["attribution"] = sc.quote_attribution or ""
            elif slide_type == SlideType.VIDEO:
                slide["video_url"] = sc.video_url or self._extract_video_url(result)
                slide["caption"] = sc.video_caption or ""
        else:
            # Fallback: generate content from existing summary data
            slide["headline"] = self._generate_headline(result)
            
            if slide_type == SlideType.BULLETS:
                slide["bullets"] = self._generate_fallback_bullets(result)
            elif slide_type == SlideType.QUOTE:
                quote_data = self._extract_best_quote(result)
                slide["quote_text"] = quote_data.get("text", "")
                slide["attribution"] = quote_data.get("attribution", "")
            elif slide_type == SlideType.VIDEO:
                slide["video_url"] = self._extract_video_url(result)
                slide["caption"] = self._generate_video_caption(result)
        
        return slide

    def _build_aggregated_slide(self, result: AggregatedResult, theme: str) -> Dict[str, Any]:
        """Build a single slide from an AggregatedResult."""
        slide_type = self._detect_aggregated_slide_type(result)
        
        # Get primary source
        primary_source = result.sources[0] if result.sources else None
        source_name = primary_source.site_name if primary_source else "Unknown"
        source_url = primary_source.url if primary_source else ""
        
        # Base slide structure
        slide: Dict[str, Any] = {
            "type": slide_type.value,
            "theme": theme,
            "source": source_name,
            "source_url": source_url,
            "source_count": result.original_count,
        }
        
        # Add all sources if multiple
        if len(result.sources) > 1:
            slide["all_sources"] = [
                {"name": s.site_name or urlparse(s.url).netloc, "url": s.url}
                for s in result.sources[:5]
            ]
        
        # Use LLM-generated slide content if available
        if result.summary and result.summary.slide_content:
            sc = result.summary.slide_content
            slide["headline"] = sc.headline
            
            if slide_type == SlideType.BULLETS:
                slide["bullets"] = sc.bullets[:5] if sc.bullets else self._generate_aggregated_fallback_bullets(result)
            elif slide_type == SlideType.QUOTE:
                slide["quote_text"] = sc.quote_text or ""
                slide["attribution"] = sc.quote_attribution or ""
            elif slide_type == SlideType.VIDEO:
                slide["video_url"] = sc.video_url or self._extract_aggregated_video_url(result)
                slide["caption"] = sc.video_caption or ""
        else:
            # Fallback
            slide["headline"] = self._generate_aggregated_headline(result)
            
            if slide_type == SlideType.BULLETS:
                slide["bullets"] = self._generate_aggregated_fallback_bullets(result)
            elif slide_type == SlideType.QUOTE:
                quote_data = self._extract_aggregated_best_quote(result)
                slide["quote_text"] = quote_data.get("text", "")
                slide["attribution"] = quote_data.get("attribution", "")
            elif slide_type == SlideType.VIDEO:
                slide["video_url"] = self._extract_aggregated_video_url(result)
                slide["caption"] = self._generate_aggregated_video_caption(result)
        
        return slide

    def _detect_slide_type(self, result: ProcessedResult) -> SlideType:
        """Detect the appropriate slide type based on content."""
        # Check if LLM already determined slide type
        if result.summary and result.summary.slide_content:
            return result.summary.slide_content.slide_type
        
        # Check for video content
        if self._has_video_content(result):
            return SlideType.VIDEO
        
        # Check for quotable content
        if self._has_quotable_content(result):
            return SlideType.QUOTE
        
        return SlideType.BULLETS

    def _detect_aggregated_slide_type(self, result: AggregatedResult) -> SlideType:
        """Detect slide type for aggregated result."""
        if result.summary and result.summary.slide_content:
            return result.summary.slide_content.slide_type
        
        # Check sources for video URLs
        for source in result.sources:
            if source.url and self._video_regex.search(source.url):
                return SlideType.VIDEO
        
        # Check for quotable content (use same criteria as _has_quotable_content)
        if result.summary and result.summary.footnotes:
            for fn in result.summary.footnotes:
                if fn.source_text and len(fn.source_text) > self.QUOTE_MIN_LENGTH and fn.context:
                    return SlideType.QUOTE
        
        return SlideType.BULLETS

    def _has_video_content(self, result: ProcessedResult) -> bool:
        """Check if result contains video references."""
        if result.url and self._video_regex.search(result.url):
            return True
        if result.raw_text and self._video_regex.search(result.raw_text):
            return True
        return False

    def _has_quotable_content(self, result: ProcessedResult) -> bool:
        """Check if result has a notable quote worth featuring."""
        if not result.summary or not result.summary.footnotes:
            return False
        
        for fn in result.summary.footnotes:
            # Look for quotes with attribution that are substantial
            if fn.source_text and len(fn.source_text) > self.QUOTE_MIN_LENGTH and fn.context:
                return True
        
        return False

    def _get_source_name(self, result: ProcessedResult) -> str:
        """Extract source name from result."""
        if result.content and result.content.site_name:
            return result.content.site_name
        parsed = urlparse(result.url or "")
        return parsed.netloc or "Unknown"

    def _generate_headline(self, result: ProcessedResult) -> str:
        """Generate a short headline from result."""
        if result.content and result.content.title:
            title = result.content.title
            # Truncate to ~8 words
            words = title.split()
            if len(words) > 8:
                return " ".join(words[:8]) + "..."
            return title
        return "Breaking News"

    def _generate_aggregated_headline(self, result: AggregatedResult) -> str:
        """Generate headline for aggregated result."""
        if result.title:
            words = result.title.split()
            if len(words) > 8:
                return " ".join(words[:8]) + "..."
            return result.title
        return "Breaking News"

    def _generate_fallback_bullets(self, result: ProcessedResult) -> List[str]:
        """Generate short bullets from key_points when slide_content not available."""
        bullets = []
        if result.summary and result.summary.key_points:
            for point in result.summary.key_points[:5]:
                # Shorten to ~10 words
                short = self._shorten_to_words(point, 10)
                bullets.append(short)
        return bullets if bullets else ["Key development in AI industry"]

    def _generate_aggregated_fallback_bullets(self, result: AggregatedResult) -> List[str]:
        """Generate bullets for aggregated result."""
        bullets = []
        if result.summary and result.summary.key_points:
            for point in result.summary.key_points[:5]:
                short = self._shorten_to_words(point, 10)
                bullets.append(short)
        return bullets if bullets else ["Key development in AI industry"]

    def _shorten_to_words(self, text: str, max_words: int) -> str:
        """Shorten text to max_words, trying to end at a natural break."""
        words = text.split()
        if len(words) <= max_words:
            return text
        
        shortened = " ".join(words[:max_words])
        # Try to end at punctuation if nearby
        for punct in ['.', ',', ':', ';', '-']:
            idx = shortened.rfind(punct)
            if idx > len(shortened) * 0.6:
                return shortened[:idx + 1].rstrip(',;:-')
        
        return shortened.rstrip('.,;:-') + "..."

    def _extract_best_quote(self, result: ProcessedResult) -> Dict[str, str]:
        """Extract the best quote from footnotes."""
        if not result.summary or not result.summary.footnotes:
            return {"text": "", "attribution": ""}
        
        best_quote = None
        for fn in result.summary.footnotes:
            if fn.source_text and len(fn.source_text) > 20:
                if best_quote is None or len(fn.source_text) > len(best_quote.source_text):
                    best_quote = fn
        
        if best_quote:
            # Shorten quote to 25 words
            quote_text = self._shorten_to_words(best_quote.source_text, 25)
            return {
                "text": quote_text,
                "attribution": best_quote.context or ""
            }
        
        return {"text": "", "attribution": ""}

    def _extract_aggregated_best_quote(self, result: AggregatedResult) -> Dict[str, str]:
        """Extract best quote from aggregated result."""
        if not result.summary or not result.summary.footnotes:
            return {"text": "", "attribution": ""}
        
        best_quote = None
        for fn in result.summary.footnotes:
            if fn.source_text and len(fn.source_text) > 20:
                if best_quote is None or len(fn.source_text) > len(best_quote.source_text):
                    best_quote = fn
        
        if best_quote:
            quote_text = self._shorten_to_words(best_quote.source_text, 25)
            return {
                "text": quote_text,
                "attribution": best_quote.context or ""
            }
        
        return {"text": "", "attribution": ""}

    def _extract_video_url(self, result: ProcessedResult) -> str:
        """Extract video URL from result."""
        # Check main URL first
        if result.url and self._video_regex.search(result.url):
            return result.url
        
        # Search in raw text for video URLs
        if result.raw_text:
            match = self._video_regex.search(result.raw_text)
            if match:
                # Try to extract full URL
                start = result.raw_text.rfind('http', 0, match.start() + 1)
                if start >= 0:
                    end = result.raw_text.find(' ', match.end())
                    if end == -1:
                        end = len(result.raw_text)
                    return result.raw_text[start:end].strip()
        
        return ""

    def _extract_aggregated_video_url(self, result: AggregatedResult) -> str:
        """Extract video URL from aggregated result."""
        for source in result.sources:
            if source.url and self._video_regex.search(source.url):
                return source.url
        return ""

    def _generate_video_caption(self, result: ProcessedResult) -> str:
        """Generate a short video caption."""
        if result.content and result.content.title:
            return self._shorten_to_words(result.content.title, 12)
        return "Watch the full video"

    def _generate_aggregated_video_caption(self, result: AggregatedResult) -> str:
        """Generate video caption for aggregated result."""
        if result.title:
            return self._shorten_to_words(result.title, 12)
        return "Watch the full video"

    def _group_by_theme(self, results: List[ProcessedResult]) -> Dict[str, List[ProcessedResult]]:
        """Group articles by detected theme."""
        grouped = defaultdict(list)
        for result in results:
            theme = detect_theme(result, use_word_boundaries=True, default_theme="Other AI News")
            grouped[theme].append(result)
        return dict(sorted(grouped.items(), key=lambda x: -len(x[1])))

    def _group_aggregated_by_theme(self, results: List[AggregatedResult]) -> Dict[str, List[AggregatedResult]]:
        """Group aggregated articles by theme."""
        grouped = defaultdict(list)
        for result in results:
            theme = self._detect_aggregated_theme(result)
            grouped[theme].append(result)
        return dict(sorted(grouped.items(), key=lambda x: -len(x[1])))

    def _detect_aggregated_theme(self, result: AggregatedResult) -> str:
        """Detect theme for aggregated result using word-boundary matching.
        
        Uses the same logic as detect_theme() from utils for consistency.
        """
        # Combine title, topics, and summary for keyword matching (same as detect_theme)
        text_parts = []
        if result.title:
            text_parts.append(result.title.lower())
        if result.summary:
            if result.summary.topics:
                text_parts.extend([t.lower() for t in result.summary.topics])
            if result.summary.executive_summary:
                text_parts.append(result.summary.executive_summary.lower())
        
        combined_text = " ".join(text_parts)
        
        # Use word boundary matching (same as detect_theme with use_word_boundaries=True)
        for theme, keywords in THEME_KEYWORDS.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', combined_text) for kw in keywords):
                return theme
        
        return "Other AI News"

    def get_filename(self) -> str:
        """Generate filename for the JSON output."""
        timestamp = datetime.now(timezone.utc).strftime("%m_%d_%y")
        return f"slides_{timestamp}.json"
