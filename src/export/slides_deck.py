"""Slides Deck Generator - Creates Markdown slides from ProcessedResult objects.

Generates structured markdown that can be imported into Google Slides, PowerPoint,
or rendered with tools like Marp, reveal.js, or Slidev.
"""

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from src.models.schemas import ProcessedResult, ProcessingStatus


class SlidesDeckGenerator:
    """
    Generate Markdown slides deck from ProcessedResult objects.
    
    Output format uses Marp-compatible markdown with --- slide separators.
    """

    def __init__(self):
        """Initialize the slides deck generator."""
        self.theme_keywords = {
            "AI Models & Releases": ["gpt", "gemini", "llm", "model", "release", "launch", "codex"],
            "AI Infrastructure": ["data center", "gpu", "nvidia", "ssd", "memory", "hardware", "chip"],
            "AI Acquisitions & Funding": ["acquire", "acquisition", "funding", "investment", "billion", "deal", "raise"],
            "AI Research & Benchmarks": ["research", "benchmark", "arc prize", "competition", "lab"],
            "AI Industry Impact": ["layoff", "job", "workforce", "industry", "enterprise"],
        }

    def generate(self, results: List[ProcessedResult]) -> str:
        """
        Generate a Markdown slides deck from processed results.

        Args:
            results: List of processed results to include.

        Returns:
            Markdown string with slide structure.
        """
        # Filter successful results
        successful = [r for r in results if r.status == ProcessingStatus.COMPLETED and r.summary]
        failed = [r for r in results if r.status == ProcessingStatus.FAILED]

        # Group by theme
        grouped = self._group_by_theme(successful)

        slides = []
        
        # Title slide
        slides.append(self._title_slide(len(successful), len(failed)))
        
        # Agenda slide
        slides.append(self._agenda_slide(grouped))
        
        # Theme sections
        for theme, articles in grouped.items():
            slides.append(self._theme_divider_slide(theme, len(articles)))
            for article in articles:
                slides.append(self._article_slide(article))
        
        # Summary slide
        slides.append(self._summary_slide(successful))
        
        # Failed URLs slide (if any)
        if failed:
            slides.append(self._failed_urls_slide(failed))

        return "\n\n---\n\n".join(slides)

    def _group_by_theme(self, results: List[ProcessedResult]) -> Dict[str, List[ProcessedResult]]:
        """Group articles by detected theme."""
        grouped = defaultdict(list)
        
        for result in results:
            theme = self._detect_theme(result)
            grouped[theme].append(result)
        
        # Sort themes by number of articles (descending)
        return dict(sorted(grouped.items(), key=lambda x: -len(x[1])))

    def _detect_theme(self, result: ProcessedResult) -> str:
        """Detect the theme of an article based on content."""
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
        
        # Match against theme keywords using word boundaries to avoid false positives
        for theme, keywords in self.theme_keywords.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', combined_text) for kw in keywords):
                return theme
        
        return "Other AI News"

    def _title_slide(self, success_count: int, fail_count: int) -> str:
        """Generate title slide."""
        date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        return f"""# AI News Briefing

## Weekly Intelligence Report

**{date}**

{success_count} articles analyzed | {fail_count} sources unavailable

<!--
Speaker Notes:
- Welcome to the AI news briefing
- {success_count} articles successfully processed
- Cover major themes: model releases, infrastructure, acquisitions
-->"""

    def _agenda_slide(self, grouped: Dict[str, List[ProcessedResult]]) -> str:
        """Generate agenda slide."""
        agenda_items = []
        for i, (theme, articles) in enumerate(grouped.items(), 1):
            agenda_items.append(f"{i}. **{theme}** ({len(articles)} articles)")
        
        agenda_list = "\n".join(agenda_items)
        
        return f"""# Agenda

{agenda_list}

<!--
Speaker Notes:
- Overview of today's coverage
- Will highlight key developments in each area
- Q&A at the end
-->"""

    def _theme_divider_slide(self, theme: str, count: int) -> str:
        """Generate theme divider slide."""
        return f"""# {theme}

## {count} Key Developments

<!--
Speaker Notes:
- Moving into {theme} section
- {count} articles to cover
-->"""

    def _article_slide(self, result: ProcessedResult) -> str:
        """Generate slide for a single article."""
        title = result.content.title if result.content and result.content.title else "Untitled"
        
        # Truncate title if too long
        if len(title) > 60:
            title = title[:57] + "..."
        
        # Get key points (limit to 4 for slide readability)
        key_points = []
        if result.summary and result.summary.key_points:
            key_points = result.summary.key_points[:4]
        
        # Format as bullet points with fallback for empty
        bullets = "\n".join([f"- {point}" for point in key_points]) if key_points else "- No key points available"
        
        # Get source info
        source = ""
        if result.content and result.content.site_name:
            source = result.content.site_name
        else:
            # Extract domain from URL safely
            parsed = urlparse(result.url or "")
            source = parsed.netloc or parsed.path.split("/")[0] or "Unknown"
        
        # Get sentiment
        sentiment = ""
        if result.summary and result.summary.sentiment:
            sentiment_map = {
                "positive": "Positive outlook",
                "negative": "Concerns raised", 
                "neutral": "Neutral coverage",
                "mixed": "Mixed perspectives"
            }
            sentiment = sentiment_map.get(result.summary.sentiment.value, "")
        
        # Executive summary for speaker notes
        exec_summary = ""
        if result.summary and result.summary.executive_summary:
            exec_summary = result.summary.executive_summary[:300]
            if len(result.summary.executive_summary) > 300:
                exec_summary += "..."
        
        return f"""## {title}

{bullets}

**Source:** {source} | **Sentiment:** {sentiment}

<!--
Speaker Notes:
{exec_summary}

URL: {result.url}
-->"""

    def _summary_slide(self, results: List[ProcessedResult]) -> str:
        """Generate summary slide with key takeaways."""
        # Collect all topics
        all_topics = []
        for r in results:
            if r.summary and r.summary.topics:
                all_topics.extend(r.summary.topics)
        
        # Get unique topics (top 6)
        unique_topics = list(dict.fromkeys(all_topics))[:6]
        topics_str = ", ".join(unique_topics) if unique_topics else "Various AI topics"
        
        # Count by sentiment
        sentiments = defaultdict(int)
        for r in results:
            if r.summary and r.summary.sentiment:
                sentiments[r.summary.sentiment.value] += 1
        
        sentiment_summary = []
        if sentiments.get("positive", 0) > 0:
            sentiment_summary.append(f"{sentiments['positive']} positive")
        if sentiments.get("negative", 0) > 0:
            sentiment_summary.append(f"{sentiments['negative']} negative")
        if sentiments.get("neutral", 0) > 0:
            sentiment_summary.append(f"{sentiments['neutral']} neutral")
        if sentiments.get("mixed", 0) > 0:
            sentiment_summary.append(f"{sentiments['mixed']} mixed")
        
        sentiment_str = ", ".join(sentiment_summary) if sentiment_summary else "Mixed coverage"
        
        return f"""# Key Takeaways

## Summary

- **{len(results)} articles** analyzed across AI industry
- **Top Topics:** {topics_str}
- **Sentiment Mix:** {sentiment_str}

## Questions?

<!--
Speaker Notes:
- Recap of major themes
- Open floor for questions
- Follow-up resources available
-->"""

    def _failed_urls_slide(self, failed: List[ProcessedResult]) -> str:
        """Generate slide listing failed URLs."""
        failed_list = []
        for r in failed:
            parsed = urlparse(r.url or "")
            domain = parsed.netloc or parsed.path.split("/")[0] or "Unknown"
            error = r.error[:50] if r.error else "Unknown error"
            failed_list.append(f"- {domain}: {error}")
        
        failed_str = "\n".join(failed_list[:10])  # Limit to 10
        
        return f"""# Sources Unavailable

The following sources could not be accessed:

{failed_str}

<!--
Speaker Notes:
- These sources had access restrictions (paywalls, bot protection)
- May need manual review or alternative sources
-->"""

    def get_filename(self) -> str:
        """Generate filename for the slides deck."""
        timestamp = datetime.now(timezone.utc).strftime("%m_%d_%y")
        return f"slides_deck_{timestamp}.md"

