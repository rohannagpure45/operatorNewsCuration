"""Prep Document Generator - Creates PDF briefing documents with 'Why It Matters' sections.

Generates professional PDF prep documents for executive briefings.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fpdf import FPDF

from src.export.utils import (
    SENTIMENT_COLORS,
    THEME_KEYWORDS,
    detect_theme,
    sanitize_text,
)
from src.models.schemas import (
    AggregatedResult,
    AggregatedResultSet,
    EntityType,
    ProcessedResult,
    ProcessingStatus,
    Sentiment,
)


class PrepDocumentGenerator:
    """
    Generate PDF prep documents with 'Why It Matters' analysis.
    
    Designed for executive briefings with concise summaries and implications.
    """

    def __init__(self):
        """Initialize the prep document generator."""
        pass

    def generate(self, results: List[ProcessedResult]) -> bytes:
        """
        Generate a PDF prep document from processed results.

        Args:
            results: List of processed results.

        Returns:
            PDF file contents as bytes.
        """
        pdf = self._create_pdf()
        
        # Filter successful results
        successful = [r for r in results if r.status == ProcessingStatus.COMPLETED and r.summary]
        failed = [r for r in results if r.status == ProcessingStatus.FAILED]
        
        # Render cover page
        self._render_cover(pdf, len(successful), len(failed))
        
        # Executive summary page
        pdf.add_page()
        self._render_executive_summary(pdf, successful)
        
        # Group by theme
        grouped = self._group_by_theme(successful)
        
        # Render each theme section
        for theme, articles in grouped.items():
            pdf.add_page()
            self._render_theme_section(pdf, theme, articles)
        
        # Appendix: Failed sources
        if failed:
            pdf.add_page()
            self._render_failed_sources(pdf, failed)
        
        return bytes(pdf.output())

    def _create_pdf(self) -> FPDF:
        """Create and configure a new FPDF instance."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        return pdf

    def _group_by_theme(self, results: List[ProcessedResult]) -> Dict[str, List[ProcessedResult]]:
        """Group articles by detected theme."""
        grouped = defaultdict(list)
        
        for result in results:
            theme = self._detect_theme(result)
            grouped[theme].append(result)
        
        return dict(sorted(grouped.items(), key=lambda x: -len(x[1])))

    def _detect_theme(self, result: ProcessedResult) -> str:
        """Detect the theme of an article based on content."""
        return detect_theme(result, use_word_boundaries=False)

    def _render_cover(self, pdf: FPDF, success_count: int, fail_count: int):
        """Render the cover page."""
        # Title
        pdf.set_y(80)
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 15, "AI Intelligence Briefing", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Subtitle
        pdf.set_font("Helvetica", size=14)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 10, "Executive Prep Document", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Date
        pdf.ln(20)
        date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, date, align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Stats box
        pdf.ln(30)
        pdf.set_fill_color(240, 249, 255)
        pdf.set_draw_color(59, 130, 246)
        
        box_width = 120
        box_x = (pdf.w - box_width) / 2
        pdf.set_xy(box_x, pdf.get_y())
        pdf.rect(box_x, pdf.get_y(), box_width, 30, style="FD")
        
        pdf.set_xy(box_x, pdf.get_y() + 8)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(box_width, 8, f"{success_count} Articles Analyzed", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(box_x)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(box_width, 6, f"{fail_count} sources unavailable", align="C")

    def _render_executive_summary(self, pdf: FPDF, results: List[ProcessedResult]):
        """Render executive summary page."""
        # Header
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 12, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(0.5)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(10)
        
        # Top themes
        grouped = self._group_by_theme(results)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, "Key Themes Covered:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        pdf.set_font("Helvetica", size=10)
        for theme, articles in grouped.items():
            pdf.set_x(25)
            pdf.set_text_color(30, 64, 175)
            pdf.cell(5, 6, ">")
            pdf.set_text_color(55, 65, 81)
            pdf.cell(0, 6, f"{theme} ({len(articles)} articles)", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(8)
        
        # Key headlines
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, "Top Headlines:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        pdf.set_font("Helvetica", size=10)
        for i, result in enumerate(results[:5], 1):
            if result.content and result.content.title:
                title = sanitize_text(result.content.title)
                if len(title) > 70:
                    title = title[:67] + "..."
                pdf.set_x(25)
                pdf.set_text_color(107, 114, 128)
                pdf.cell(8, 6, f"{i}.")
                pdf.set_text_color(55, 65, 81)
                pdf.multi_cell(pdf.w - 55, 6, title)
        
        pdf.ln(8)
        
        # Sentiment breakdown
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, "Sentiment Analysis:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        sentiments = defaultdict(int)
        for r in results:
            if r.summary and r.summary.sentiment:
                sentiments[r.summary.sentiment] += 1
        
        pdf.set_font("Helvetica", size=10)
        for sentiment, count in sentiments.items():
            color = SENTIMENT_COLORS.get(sentiment, (107, 114, 128))
            pdf.set_x(25)
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
            label = sentiment.value.title()
            badge_width = pdf.get_string_width(label) + 8
            pdf.cell(badge_width, 6, label, fill=True)
            pdf.set_text_color(55, 65, 81)
            pdf.cell(20, 6, f"  {count} articles")
            pdf.ln(8)

    def _render_theme_section(self, pdf: FPDF, theme: str, articles: List[ProcessedResult]):
        """Render a theme section with articles."""
        # Theme header
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 12, theme, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(0.3)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(8)
        
        # Render each article
        for article in articles:
            self._render_article_brief(pdf, article)
            pdf.ln(5)

    def _render_article_brief(self, pdf: FPDF, result: ProcessedResult):
        """Render a single article brief with 'Why It Matters'."""
        # Check if we need a new page
        if pdf.get_y() > 220:
            pdf.add_page()
        
        # Article title
        title = "Untitled"
        if result.content and result.content.title:
            title = sanitize_text(result.content.title)
        
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(17, 24, 39)
        pdf.multi_cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        
        # Source and sentiment
        source = ""
        if result.content and result.content.site_name:
            source = result.content.site_name
        else:
            parsed = urlparse(result.url or "")
            source = parsed.netloc or parsed.path.split("/")[0] or "Unknown"
        
        pdf.set_font("Helvetica", size=8)
        pdf.set_text_color(107, 114, 128)
        
        sentiment_text = ""
        if result.summary and result.summary.sentiment:
            sentiment_text = f" | Sentiment: {result.summary.sentiment.value.title()}"
        
        # Source with hyperlink
        pdf.cell(pdf.get_string_width("Source: ") + 1, 5, "Source: ", new_x="RIGHT", new_y="TOP")
        pdf.set_text_color(59, 130, 246)  # Blue link color
        # Truncate source name if too long (max ~40 chars to leave room for sentiment)
        if len(source) > 40:
            source = source[:37] + "..."
        pdf.cell(pdf.get_string_width(source) + 1, 5, source, link=result.url, new_x="RIGHT", new_y="TOP")
        pdf.set_text_color(107, 114, 128)  # Reset to gray
        pdf.cell(0, 5, sentiment_text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        # Summary box
        if result.summary and result.summary.executive_summary:
            pdf.set_fill_color(249, 250, 251)
            y_start = pdf.get_y()
            
            summary = sanitize_text(result.summary.executive_summary)
            if len(summary) > 300:
                summary = summary[:297] + "..."
            
            pdf.set_x(25)
            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(55, 65, 81)
            pdf.multi_cell(pdf.w - 50, 5, summary)
            
            y_end = pdf.get_y()
            pdf.rect(22, y_start - 2, pdf.w - 44, y_end - y_start + 4, style="D")
        
        pdf.ln(4)
        
        # Key Points (bullet points)
        if result.summary and result.summary.key_points:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(55, 65, 81)
            pdf.cell(0, 5, "Key Points:", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("Helvetica", size=9)
            for point in result.summary.key_points[:3]:
                point = sanitize_text(point)
                if len(point) > 100:
                    point = point[:97] + "..."
                pdf.set_x(25)
                pdf.cell(5, 5, "-")
                pdf.multi_cell(pdf.w - 55, 5, point)
        
        pdf.ln(3)
        
        # WHY IT MATTERS section
        self._render_why_it_matters(pdf, result)
        
        # Separator line
        pdf.set_draw_color(229, 231, 235)
        pdf.line(20, pdf.get_y() + 3, pdf.w - 20, pdf.get_y() + 3)
        pdf.ln(6)

    def _render_why_it_matters(self, pdf: FPDF, result: ProcessedResult):
        """Render the 'Why It Matters' section."""
        y_start = pdf.get_y()
        
        # Generate implications text first
        implications_text = self._generate_why_it_matters(result)
        implications_text = sanitize_text(implications_text)
        
        # Calculate dimensions needed for the box
        header_height = 6
        # Estimate text height based on string width and available width
        text_width = pdf.w - 50
        pdf.set_font("Helvetica", size=9)
        # Approximate lines needed (each line ~text_width characters)
        text_lines = max(1, int(len(implications_text) / (text_width * 0.35)) + 1)
        text_height = text_lines * 5
        total_height = header_height + text_height + 4
        
        # Draw background first
        pdf.set_fill_color(254, 252, 232)  # Light yellow
        pdf.set_draw_color(250, 204, 21)   # Yellow border
        pdf.rect(20, y_start - 2, pdf.w - 40, total_height, style="FD")
        
        # Render text on top of background (once)
        pdf.set_xy(22, y_start)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(161, 98, 7)  # Amber text
        pdf.cell(0, 6, "WHY IT MATTERS", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(25)
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(120, 53, 15)  # Darker amber
        pdf.multi_cell(pdf.w - 50, 5, implications_text)
        
        # Ensure we're at least past the box
        if pdf.get_y() < y_start + total_height - 2:
            pdf.set_y(y_start + total_height - 2)

    def _generate_why_it_matters(self, result: ProcessedResult) -> str:
        """Generate 'Why It Matters' text from article implications."""
        # Use implications if available
        if result.summary and result.summary.implications:
            return " ".join(result.summary.implications[:2])
        
        # Fallback: Generate from key points and topics
        parts = []
        
        if result.summary:
            # Extract key entities for context
            if result.summary.entities:
                orgs = [e.text for e in result.summary.entities if e.type == EntityType.ORG][:2]
                if orgs:
                    parts.append(f"Impacts {', '.join(orgs)}.")
            
            # Add sentiment-based implication
            if result.summary.sentiment == Sentiment.POSITIVE:
                parts.append("This development signals positive momentum in the AI industry.")
            elif result.summary.sentiment == Sentiment.NEGATIVE:
                parts.append("This raises concerns that stakeholders should monitor closely.")
            elif result.summary.sentiment == Sentiment.MIXED:
                parts.append("This presents both opportunities and challenges for the industry.")
            else:
                parts.append("This is a notable development worth tracking.")
        
        return " ".join(parts) if parts else "Industry development worth monitoring."

    def _render_failed_sources(self, pdf: FPDF, failed: List[ProcessedResult]):
        """Render appendix with failed sources."""
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(239, 68, 68)
        pdf.cell(0, 10, "Appendix: Unavailable Sources", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(239, 68, 68)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(8)
        
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(107, 114, 128)
        pdf.multi_cell(0, 5, "The following sources could not be accessed due to paywalls, bot protection, or other restrictions:")
        pdf.ln(5)
        
        for result in failed:
            parsed = urlparse(result.url or "")
            domain = parsed.netloc or parsed.path.split("/")[0] or "Unknown"
            error = sanitize_text(result.error[:60]) if result.error else "Unknown error"
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(55, 65, 81)
            pdf.cell(0, 5, domain, new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("Helvetica", size=8)
            pdf.set_text_color(239, 68, 68)
            pdf.cell(0, 4, f"Error: {error}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    def get_filename(self) -> str:
        """Generate filename for the prep document."""
        timestamp = datetime.now(timezone.utc).strftime("%m_%d_%y")
        return f"prep_document_{timestamp}.pdf"

    def generate_aggregated(self, result_set: AggregatedResultSet) -> bytes:
        """
        Generate a PDF prep document from aggregated results.

        Args:
            result_set: AggregatedResultSet with merged/deduplicated results.

        Returns:
            PDF file contents as bytes.
        """
        pdf = self._create_pdf()
        
        # Filter successful results
        successful = [r for r in result_set.results if r.status == ProcessingStatus.COMPLETED and r.summary]
        
        # Render cover page with aggregation stats
        self._render_aggregated_cover(pdf, result_set)
        
        # Executive summary page
        pdf.add_page()
        self._render_aggregated_executive_summary(pdf, successful, result_set)
        
        # Group by theme
        grouped = self._group_aggregated_by_theme(successful)
        
        # Render each theme section
        for theme, articles in grouped.items():
            pdf.add_page()
            self._render_aggregated_theme_section(pdf, theme, articles)
        
        return bytes(pdf.output())

    def _render_aggregated_cover(self, pdf: FPDF, result_set: AggregatedResultSet):
        """Render the cover page for aggregated results."""
        # Title
        pdf.set_y(80)
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 15, "AI Intelligence Briefing", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Subtitle
        pdf.set_font("Helvetica", size=14)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 10, "Executive Prep Document", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Date
        pdf.ln(20)
        date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, date, align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Stats box
        pdf.ln(30)
        pdf.set_fill_color(240, 249, 255)
        pdf.set_draw_color(59, 130, 246)
        
        box_width = 140
        box_x = (pdf.w - box_width) / 2
        pdf.set_xy(box_x, pdf.get_y())
        pdf.rect(box_x, pdf.get_y(), box_width, 45, style="FD")
        
        pdf.set_xy(box_x, pdf.get_y() + 8)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(box_width, 8, f"{result_set.total_original} Articles Analyzed", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(box_x)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(34, 197, 94)  # Green
        pdf.cell(box_width, 7, f"{result_set.total_aggregated} Unique Stories", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(box_x)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(box_width, 6, f"{result_set.duplicates_merged} duplicates merged", align="C")

    def _group_aggregated_by_theme(self, results: List[AggregatedResult]) -> Dict[str, List[AggregatedResult]]:
        """Group aggregated articles by detected theme."""
        grouped = defaultdict(list)
        
        for result in results:
            theme = self._detect_aggregated_theme(result)
            grouped[theme].append(result)
        
        return dict(sorted(grouped.items(), key=lambda x: -len(x[1])))

    def _detect_aggregated_theme(self, result: AggregatedResult) -> str:
        """Detect the theme of an aggregated article based on content."""
        # Check topics for theme detection
        if result.summary and result.summary.topics:
            topics_lower = " ".join(result.summary.topics).lower()
            title_lower = result.title.lower() if result.title else ""
            combined = topics_lower + " " + title_lower
            
            from src.export.utils import THEME_KEYWORDS
            for theme, keywords in THEME_KEYWORDS.items():
                for kw in keywords:
                    if kw.lower() in combined:
                        return theme
        
        return "Other AI News"

    def _render_aggregated_executive_summary(self, pdf: FPDF, results: List[AggregatedResult], result_set: AggregatedResultSet):
        """Render executive summary page for aggregated results."""
        # Header
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 12, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(0.5)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(10)
        
        # Top themes
        grouped = self._group_aggregated_by_theme(results)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, "Key Themes Covered:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        pdf.set_font("Helvetica", size=10)
        for theme, articles in grouped.items():
            pdf.set_x(25)
            pdf.set_text_color(30, 64, 175)
            pdf.cell(5, 6, ">")
            pdf.set_text_color(55, 65, 81)
            pdf.cell(0, 6, f"{theme} ({len(articles)} stories)", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(8)
        
        # Key headlines
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, "Top Headlines:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        pdf.set_font("Helvetica", size=10)
        for i, result in enumerate(results[:5], 1):
            title = sanitize_text(result.title)
            if len(title) > 70:
                title = title[:67] + "..."
            pdf.set_x(25)
            pdf.set_text_color(107, 114, 128)
            pdf.cell(8, 6, f"{i}.")
            pdf.set_text_color(55, 65, 81)
            pdf.multi_cell(pdf.w - 55, 6, title)
            
            # Show source count if aggregated
            if result.original_count > 1:
                pdf.set_x(33)
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(107, 114, 128)
                pdf.cell(0, 4, f"({result.original_count} sources)", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", size=10)
        
        pdf.ln(8)
        
        # Sentiment breakdown
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, "Sentiment Analysis:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        
        sentiments = defaultdict(int)
        for r in results:
            if r.summary and r.summary.sentiment:
                sentiments[r.summary.sentiment] += 1
        
        pdf.set_font("Helvetica", size=10)
        for sentiment, count in sentiments.items():
            color = SENTIMENT_COLORS.get(sentiment, (107, 114, 128))
            pdf.set_x(25)
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
            label = sentiment.value.title()
            badge_width = pdf.get_string_width(label) + 8
            pdf.cell(badge_width, 6, label, fill=True)
            pdf.set_text_color(55, 65, 81)
            pdf.cell(20, 6, f"  {count} stories")
            pdf.ln(8)

    def _render_aggregated_theme_section(self, pdf: FPDF, theme: str, articles: List[AggregatedResult]):
        """Render a theme section with aggregated articles."""
        # Theme header
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 12, theme, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(0.3)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(8)
        
        # Render each article
        for article in articles:
            self._render_aggregated_article_brief(pdf, article)
            pdf.ln(5)

    def _render_aggregated_article_brief(self, pdf: FPDF, result: AggregatedResult):
        """Render a single aggregated article brief with 'Why It Matters'."""
        # Check if we need a new page
        if pdf.get_y() > 220:
            pdf.add_page()
        
        # Article title
        title = sanitize_text(result.title)
        
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(17, 24, 39)
        pdf.multi_cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        
        # Aggregation badge if multiple sources
        if result.original_count > 1:
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_fill_color(34, 197, 94)  # Green
            pdf.set_text_color(255, 255, 255)
            badge_text = f"{result.original_count} Sources"
            badge_width = pdf.get_string_width(badge_text) + 6
            pdf.cell(badge_width, 4, badge_text, fill=True, new_x="RIGHT")
            pdf.ln(6)
        
        # Sources section
        if result.sources:
            pdf.set_font("Helvetica", size=8)
            pdf.set_text_color(107, 114, 128)
            pdf.cell(pdf.get_string_width("Sources: ") + 1, 5, "Sources: ", new_x="RIGHT", new_y="TOP")
            
            # List source names with links
            source_names = []
            for source in result.sources[:3]:  # Limit to 3 sources in brief view
                site = source.site_name or urlparse(source.url).netloc or "Unknown"
                source_names.append(site)
            
            sources_text = ", ".join(source_names)
            if len(result.sources) > 3:
                sources_text += f" +{len(result.sources) - 3} more"
            
            pdf.set_text_color(59, 130, 246)  # Blue link color
            # Link to first source
            pdf.cell(0, 5, sources_text, link=result.sources[0].url if result.sources else "", new_x="LMARGIN", new_y="NEXT")
        
        # Sentiment
        sentiment_text = ""
        if result.summary and result.summary.sentiment:
            sentiment_text = f"Sentiment: {result.summary.sentiment.value.title()}"
            pdf.set_font("Helvetica", size=8)
            pdf.set_text_color(107, 114, 128)
            pdf.cell(0, 5, sentiment_text, new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(3)
        
        # Summary box
        if result.summary and result.summary.executive_summary:
            pdf.set_fill_color(249, 250, 251)
            y_start = pdf.get_y()
            
            summary = sanitize_text(result.summary.executive_summary)
            if len(summary) > 400:
                summary = summary[:397] + "..."
            
            pdf.set_x(25)
            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(55, 65, 81)
            pdf.multi_cell(pdf.w - 50, 5, summary)
            
            y_end = pdf.get_y()
            pdf.rect(22, y_start - 2, pdf.w - 44, y_end - y_start + 4, style="D")
        
        pdf.ln(4)
        
        # Key Points (bullet points)
        if result.summary and result.summary.key_points:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(55, 65, 81)
            pdf.cell(0, 5, "Key Points:", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("Helvetica", size=9)
            # Show more key points for aggregated results
            max_points = 5 if result.original_count > 1 else 3
            for point in result.summary.key_points[:max_points]:
                point = sanitize_text(point)
                if len(point) > 100:
                    point = point[:97] + "..."
                pdf.set_x(25)
                pdf.cell(5, 5, "-")
                pdf.multi_cell(pdf.w - 55, 5, point)
        
        pdf.ln(3)
        
        # WHY IT MATTERS section
        self._render_aggregated_why_it_matters(pdf, result)
        
        # Separator line
        pdf.set_draw_color(229, 231, 235)
        pdf.line(20, pdf.get_y() + 3, pdf.w - 20, pdf.get_y() + 3)
        pdf.ln(6)

    def _render_aggregated_why_it_matters(self, pdf: FPDF, result: AggregatedResult):
        """Render the 'Why It Matters' section for aggregated result."""
        y_start = pdf.get_y()
        
        # Generate implications text
        implications_text = self._generate_aggregated_why_it_matters(result)
        implications_text = sanitize_text(implications_text)
        
        # Calculate dimensions
        header_height = 6
        text_width = pdf.w - 50
        pdf.set_font("Helvetica", size=9)
        text_lines = max(1, int(len(implications_text) / (text_width * 0.35)) + 1)
        text_height = text_lines * 5
        total_height = header_height + text_height + 4
        
        # Draw background
        pdf.set_fill_color(254, 252, 232)
        pdf.set_draw_color(250, 204, 21)
        pdf.rect(20, y_start - 2, pdf.w - 40, total_height, style="FD")
        
        # Render text
        pdf.set_xy(22, y_start)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(161, 98, 7)
        pdf.cell(0, 6, "WHY IT MATTERS", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(25)
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(120, 53, 15)
        pdf.multi_cell(pdf.w - 50, 5, implications_text)
        
        if pdf.get_y() < y_start + total_height - 2:
            pdf.set_y(y_start + total_height - 2)

    def _generate_aggregated_why_it_matters(self, result: AggregatedResult) -> str:
        """Generate 'Why It Matters' text from aggregated article implications."""
        # Use implications if available
        if result.summary and result.summary.implications:
            return " ".join(result.summary.implications[:2])
        
        # Fallback
        parts = []
        
        if result.summary:
            if result.summary.entities:
                orgs = [e.text for e in result.summary.entities if e.type == EntityType.ORG][:2]
                if orgs:
                    parts.append(f"Impacts {', '.join(orgs)}.")
            
            if result.summary.sentiment == Sentiment.POSITIVE:
                parts.append("This development signals positive momentum in the AI industry.")
            elif result.summary.sentiment == Sentiment.NEGATIVE:
                parts.append("This raises concerns that stakeholders should monitor closely.")
            elif result.summary.sentiment == Sentiment.MIXED:
                parts.append("This presents both opportunities and challenges for the industry.")
            else:
                parts.append("This is a notable development worth tracking.")
        
        return " ".join(parts) if parts else "Industry development worth monitoring."

