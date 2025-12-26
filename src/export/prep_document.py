"""Prep Document Generator - Creates PDF briefing documents with 'Why It Matters' sections.

Generates professional PDF prep documents for executive briefings.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fpdf import FPDF

from src.models.schemas import ProcessedResult, ProcessingStatus, Sentiment


def sanitize_text(obj):
    """Recursively replace unicode chars that fpdf can't handle."""
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


class PrepDocumentGenerator:
    """
    Generate PDF prep documents with 'Why It Matters' analysis.
    
    Designed for executive briefings with concise summaries and implications.
    """

    # Theme keywords for grouping
    THEME_KEYWORDS = {
        "AI Models & Product Launches": ["gpt", "gemini", "llm", "model", "release", "launch", "codex", "claude"],
        "AI Infrastructure & Hardware": ["data center", "gpu", "nvidia", "ssd", "memory", "hardware", "chip", "hynix"],
        "AI M&A and Funding": ["acquire", "acquisition", "funding", "investment", "billion", "deal", "raise", "groq"],
        "AI Research & Competitions": ["research", "benchmark", "arc prize", "competition", "lab", "scientific"],
        "AI Workforce & Industry": ["layoff", "job", "workforce", "industry", "enterprise", "hiring"],
    }

    # Sentiment colors
    SENTIMENT_COLORS = {
        Sentiment.POSITIVE: (34, 197, 94),
        Sentiment.NEGATIVE: (239, 68, 68),
        Sentiment.NEUTRAL: (107, 114, 128),
        Sentiment.MIXED: (245, 158, 11),
    }

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
        text_parts = []
        if result.content and result.content.title:
            text_parts.append(result.content.title.lower())
        if result.summary:
            if result.summary.topics:
                text_parts.extend([t.lower() for t in result.summary.topics])
            if result.summary.executive_summary:
                text_parts.append(result.summary.executive_summary.lower())
        
        combined_text = " ".join(text_parts)
        
        for theme, keywords in self.THEME_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                return theme
        
        return "Other AI Developments"

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
        date = datetime.now().strftime("%B %d, %Y")
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
            color = self.SENTIMENT_COLORS.get(sentiment, (107, 114, 128))
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
            source = result.url.split("//")[-1].split("/")[0]
        
        pdf.set_font("Helvetica", size=8)
        pdf.set_text_color(107, 114, 128)
        
        sentiment_text = ""
        if result.summary and result.summary.sentiment:
            sentiment_text = f" | Sentiment: {result.summary.sentiment.value.title()}"
        
        pdf.cell(0, 5, f"Source: {source}{sentiment_text}", new_x="LMARGIN", new_y="NEXT")
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
        pdf.set_fill_color(254, 252, 232)  # Light yellow
        pdf.set_draw_color(250, 204, 21)   # Yellow border
        
        y_start = pdf.get_y()
        
        pdf.set_x(22)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(161, 98, 7)  # Amber text
        pdf.cell(0, 6, "WHY IT MATTERS", new_x="LMARGIN", new_y="NEXT")
        
        # Generate implications text
        implications_text = self._generate_why_it_matters(result)
        implications_text = sanitize_text(implications_text)
        
        pdf.set_x(25)
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(120, 53, 15)  # Darker amber
        pdf.multi_cell(pdf.w - 50, 5, implications_text)
        
        y_end = pdf.get_y()
        
        # Draw background
        pdf.set_xy(20, y_start - 2)
        pdf.rect(20, y_start - 2, pdf.w - 40, y_end - y_start + 4, style="FD")
        
        # Re-render text on top of background
        pdf.set_xy(22, y_start)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(161, 98, 7)
        pdf.cell(0, 6, "WHY IT MATTERS", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(25)
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(120, 53, 15)
        pdf.multi_cell(pdf.w - 50, 5, implications_text)

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
                orgs = [e.text for e in result.summary.entities if e.type.value == "ORG"][:2]
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
            domain = result.url.split("//")[-1].split("/")[0]
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
        timestamp = datetime.now().strftime("%m_%d_%y")
        return f"prep_document_{timestamp}.pdf"

