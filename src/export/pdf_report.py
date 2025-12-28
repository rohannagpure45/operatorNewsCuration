"""PDF Report Generator using fpdf2.

Generates professional PDF reports from ProcessedResult objects.
"""

import html as html_module
import re
from datetime import datetime, timezone
from typing import List, Optional

from fpdf import FPDF

from src.export.utils import (
    ENTITY_COLORS,
    RATING_COLORS,
    SENTIMENT_COLORS,
    SENTIMENT_LABELS,
)
from src.models.schemas import (
    ProcessedResult,
    ProcessingStatus,
)


class PDFReportGenerator:
    """
    Generate professional PDF reports from ProcessedResult objects.
    
    Uses fpdf2 for pure-Python PDF generation.
    """

    def __init__(self):
        """Initialize the PDF report generator."""
        pass

    def generate(self, result: ProcessedResult) -> bytes:
        """
        Generate a PDF report from a ProcessedResult.

        Args:
            result: The processed result to generate a report for.

        Returns:
            PDF file contents as bytes.
        """
        pdf = self._create_pdf()
        self._render_result(pdf, result)
        return bytes(pdf.output())

    def generate_batch(self, results: List[ProcessedResult]) -> bytes:
        """
        Generate a single PDF report containing multiple results.

        Args:
            results: List of processed results to include in the report.

        Returns:
            PDF file contents as bytes.
        """
        pdf = self._create_pdf()
        for i, result in enumerate(results):
            if i > 0:
                pdf.add_page()
            self._render_result(pdf, result, skip_header=(i > 0))
        return bytes(pdf.output())

    def get_filename(self, result: ProcessedResult) -> str:
        """
        Generate a safe filename for the PDF.

        Args:
            result: The processed result.

        Returns:
            A safe filename string ending in .pdf
        """
        # Try to use the title, otherwise use URL
        if result.content and result.content.title:
            base = result.content.title
        else:
            # Extract domain from URL
            base = result.url.split("//")[-1].split("/")[0]

        # Sanitize the filename
        safe = re.sub(r'[^\w\s-]', '', base)
        safe = re.sub(r'[-\s]+', '-', safe).strip('-')
        safe = safe[:50]  # Limit length

        if not safe:
            safe = "report"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe}_{timestamp}.pdf"

    def _create_pdf(self) -> FPDF:
        """Create and configure a new FPDF instance."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        
        # Set up fonts
        pdf.set_font("Helvetica", size=10)
        
        return pdf

    def _render_result(self, pdf: FPDF, result: ProcessedResult, skip_header: bool = False):
        """Render a single ProcessedResult to the PDF."""
        if not skip_header:
            self._render_report_header(pdf)

        self._render_article_header(pdf, result)

        if result.status == ProcessingStatus.FAILED:
            self._render_error_section(pdf, result)
            return

        if result.summary:
            self._render_summary_section(pdf, result)
            self._render_key_points_section(pdf, result)

            if result.summary.entities:
                self._render_entities_section(pdf, result)

            if result.summary.implications:
                self._render_implications_section(pdf, result)

            if result.summary.footnotes:
                self._render_footnotes_section(pdf, result)

        if result.fact_check:
            self._render_fact_check_section(pdf, result)

        self._render_metadata_footer(pdf, result)

    def _render_report_header(self, pdf: FPDF):
        """Render the main report header."""
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(30, 64, 175)  # Blue
        pdf.cell(0, 15, "News Curation Report", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(107, 114, 128)  # Gray
        generated = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        pdf.cell(0, 8, f"Generated: {generated}", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Separator line
        pdf.set_draw_color(59, 130, 246)
        pdf.set_line_width(0.5)
        pdf.line(20, pdf.get_y() + 5, pdf.w - 20, pdf.get_y() + 5)
        pdf.ln(15)

    def _render_article_header(self, pdf: FPDF, result: ProcessedResult):
        """Render the article header section."""
        # Title
        title = "Untitled"
        if result.content and result.content.title:
            title = result.content.title

        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(17, 24, 39)  # Dark gray
        pdf.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Topics
        if result.summary and result.summary.topics:
            pdf.set_font("Helvetica", size=9)
            for topic in result.summary.topics:
                pdf.set_fill_color(219, 234, 254)  # Light blue
                pdf.set_text_color(30, 64, 175)
                pdf.cell(pdf.get_string_width(topic) + 8, 6, topic, fill=True, new_x="RIGHT")
                pdf.cell(3)  # spacing
            pdf.ln(8)

        # Metadata
        meta_items = []
        if result.content:
            if result.content.author:
                meta_items.append(f"Author: {result.content.author}")
            if result.content.published_date:
                meta_items.append(f"Published: {result.content.published_date.strftime('%B %d, %Y')}")
            if result.content.site_name:
                meta_items.append(f"Source: {result.content.site_name}")
            if result.content.word_count:
                meta_items.append(f"{result.content.word_count:,} words")

        if meta_items:
            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(107, 114, 128)
            pdf.cell(0, 6, " | ".join(meta_items), new_x="LMARGIN", new_y="NEXT")

        # Source URL
        pdf.set_font("Helvetica", size=8)
        pdf.set_text_color(156, 163, 175)
        pdf.cell(0, 5, f"URL: {result.url[:80]}{'...' if len(result.url) > 80 else ''}", 
                 new_x="LMARGIN", new_y="NEXT")
        
        # Separator
        pdf.set_draw_color(229, 231, 235)
        pdf.line(20, pdf.get_y() + 3, pdf.w - 20, pdf.get_y() + 3)
        pdf.ln(8)

    def _render_error_section(self, pdf: FPDF, result: ProcessedResult):
        """Render error section for failed results."""
        pdf.set_fill_color(254, 242, 242)  # Light red background
        pdf.set_draw_color(254, 202, 202)  # Red border
        
        y_start = pdf.get_y()
        pdf.rect(20, y_start, pdf.w - 40, 25, style="FD")
        
        pdf.set_xy(25, y_start + 5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(220, 38, 38)
        pdf.cell(0, 6, "Processing Failed", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_x(25)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(127, 29, 29)
        error_msg = result.error or "Unknown error occurred"
        pdf.multi_cell(pdf.w - 50, 5, error_msg)
        pdf.ln(10)

    def _render_summary_section(self, pdf: FPDF, result: ProcessedResult):
        """Render the executive summary section."""
        if not result.summary:
            return

        # Section header
        self._render_section_header(pdf, "Executive Summary")

        # Sentiment badge (top right)
        sentiment = result.summary.sentiment
        sentiment_color = SENTIMENT_COLORS.get(sentiment, (107, 114, 128))
        sentiment_label = SENTIMENT_LABELS.get(sentiment, "Unknown")

        # Draw sentiment badge
        badge_width = pdf.get_string_width(sentiment_label) + 10
        badge_x = pdf.w - 20 - badge_width
        badge_y = pdf.get_y() - 6
        
        pdf.set_fill_color(*sentiment_color)
        pdf.set_xy(badge_x, badge_y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(badge_width, 6, sentiment_label, fill=True, align="C")

        # Summary text with background
        pdf.set_xy(20, pdf.get_y() + 2)
        pdf.set_fill_color(240, 249, 255)  # Light blue background
        pdf.set_draw_color(59, 130, 246)   # Blue border
        
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(55, 65, 81)
        
        # Calculate height needed for the text
        summary_text = result.summary.executive_summary
        y_start = pdf.get_y()
        pdf.set_x(25)
        pdf.multi_cell(pdf.w - 50, 6, summary_text)
        y_end = pdf.get_y()
        
        # Draw background rectangle
        pdf.set_xy(20, y_start - 3)
        pdf.rect(20, y_start - 3, pdf.w - 40, y_end - y_start + 6, style="D")
        
        pdf.set_y(y_end + 8)

    def _render_key_points_section(self, pdf: FPDF, result: ProcessedResult):
        """Render the key points section."""
        if not result.summary or not result.summary.key_points:
            return

        self._render_section_header(pdf, "Key Points")

        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(55, 65, 81)

        for i, point in enumerate(result.summary.key_points, 1):
            pdf.set_x(25)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(8, 6, f"{i}.")
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(pdf.w - 55, 6, point)
            pdf.ln(1)

        pdf.ln(5)

    def _render_entities_section(self, pdf: FPDF, result: ProcessedResult):
        """Render the entities section."""
        if not result.summary or not result.summary.entities:
            return

        self._render_section_header(pdf, "Key Entities")

        # Create a simple table
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(249, 250, 251)
        pdf.set_text_color(55, 65, 81)
        
        col_width = (pdf.w - 40) / 2
        pdf.set_x(20)
        pdf.cell(col_width, 7, "Entity", border=1, fill=True)
        pdf.cell(col_width, 7, "Type", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", size=9)
        for entity in result.summary.entities:
            pdf.set_x(20)
            pdf.cell(col_width, 7, entity.text[:40], border=1)
            
            entity_type = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)
            color = ENTITY_COLORS.get(entity_type, (240, 240, 240))
            pdf.set_fill_color(*color)
            pdf.cell(col_width, 7, entity_type, border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(8)

    def _render_implications_section(self, pdf: FPDF, result: ProcessedResult):
        """Render the implications section."""
        if not result.summary or not result.summary.implications:
            return

        self._render_section_header(pdf, "Implications")

        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(55, 65, 81)

        for imp in result.summary.implications:
            pdf.set_x(25)
            pdf.cell(5, 6, ">")  # Arrow indicator
            pdf.multi_cell(pdf.w - 55, 6, imp)
            pdf.ln(1)

        pdf.ln(5)

    def _render_footnotes_section(self, pdf: FPDF, result: ProcessedResult):
        """Render the footnotes section."""
        if not result.summary or not result.summary.footnotes:
            return

        self._render_section_header(pdf, "Citations & Footnotes")

        pdf.set_font("Helvetica", size=9)

        for fn in result.summary.footnotes:
            pdf.set_fill_color(249, 250, 251)
            y_start = pdf.get_y()
            
            pdf.set_x(25)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(59, 130, 246)
            pdf.cell(10, 5, f"[{fn.id}]")
            
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(75, 85, 99)
            pdf.multi_cell(pdf.w - 60, 5, f'"{fn.source_text}"')
            
            pdf.set_x(35)
            pdf.set_font("Helvetica", size=8)
            pdf.set_text_color(107, 114, 128)
            pdf.multi_cell(pdf.w - 60, 4, fn.context)
            
            pdf.ln(3)

        pdf.ln(5)

    def _render_fact_check_section(self, pdf: FPDF, result: ProcessedResult):
        """Render the fact-check section."""
        fc = result.fact_check
        if not fc:
            return

        # Section with yellow background
        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(252, 211, 77)
        
        y_start = pdf.get_y()
        
        self._render_section_header(pdf, "Fact-Check Results")
        
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(107, 114, 128)
        pdf.set_x(20)
        pdf.cell(0, 5, f"Claims analyzed: {fc.claims_analyzed}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Verified claims
        if fc.verified_claims:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(34, 197, 94)
            pdf.set_x(20)
            pdf.cell(0, 6, "Verified Claims", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            for claim in fc.verified_claims:
                self._render_verified_claim(pdf, claim)

        # Unverified claims
        if fc.unverified_claims:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(107, 114, 128)
            pdf.set_x(20)
            pdf.cell(0, 6, "Unverified Claims", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(107, 114, 128)
            for claim in fc.unverified_claims:
                pdf.set_x(25)
                pdf.cell(5, 5, "-")  # Bullet
                pdf.multi_cell(pdf.w - 55, 5, claim)

        # Publisher credibility
        if fc.publisher_credibility:
            cred = fc.publisher_credibility
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(55, 65, 81)
            pdf.set_x(20)
            pdf.cell(0, 6, "Publisher Credibility", new_x="LMARGIN", new_y="NEXT")

            if cred.score is not None:
                # Draw progress bar
                bar_width = 100
                bar_height = 8
                pdf.set_x(20)
                
                # Background
                pdf.set_fill_color(229, 231, 235)
                pdf.rect(20, pdf.get_y(), bar_width, bar_height, style="F")
                
                # Filled portion
                pdf.set_fill_color(34, 197, 94)
                pdf.rect(20, pdf.get_y(), bar_width * cred.score / 100, bar_height, style="F")
                
                pdf.set_xy(125, pdf.get_y())
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(55, 65, 81)
                pdf.cell(0, bar_height, f"{cred.score}/100", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(107, 114, 128)
            pdf.set_x(20)
            pdf.cell(0, 5, f"Source: {cred.source}", new_x="LMARGIN", new_y="NEXT")
            
            if cred.notes:
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_x(20)
                pdf.multi_cell(pdf.w - 40, 4, cred.notes)

        pdf.ln(8)

    def _render_verified_claim(self, pdf: FPDF, claim):
        """Render a single verified claim."""
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(229, 231, 235)
        
        y_start = pdf.get_y()
        
        # Claim text
        pdf.set_x(25)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(55, 65, 81)
        pdf.multi_cell(pdf.w - 55, 5, claim.claim)
        
        # Rating badge
        rating_color = RATING_COLORS.get(claim.rating, (107, 114, 128))
        rating_label = claim.rating.value.replace("_", " ").title()
        
        pdf.set_fill_color(*rating_color)
        pdf.set_x(25)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(255, 255, 255)
        badge_width = pdf.get_string_width(rating_label) + 8
        pdf.cell(badge_width, 5, rating_label, fill=True)
        pdf.ln(3)
        
        # Source
        pdf.set_x(25)
        pdf.set_font("Helvetica", size=8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 4, f"Source: {claim.source}", new_x="LMARGIN", new_y="NEXT")
        
        # Explanation
        if claim.explanation:
            pdf.set_x(25)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(75, 85, 99)
            pdf.multi_cell(pdf.w - 55, 4, claim.explanation)
        
        pdf.ln(5)

    def _render_metadata_footer(self, pdf: FPDF, result: ProcessedResult):
        """Render processing metadata footer."""
        pdf.set_draw_color(229, 231, 235)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(5)
        
        meta_items = [f"Source Type: {result.source_type.value}"]
        
        if result.extracted_at:
            meta_items.append(f"Extracted: {result.extracted_at.strftime('%Y-%m-%d %H:%M UTC')}")
        
        if result.processing_time_ms:
            meta_items.append(f"Processing Time: {result.processing_time_ms}ms")

        pdf.set_font("Helvetica", size=8)
        pdf.set_text_color(156, 163, 175)
        pdf.cell(0, 4, " | ".join(meta_items), align="L", new_x="LMARGIN", new_y="NEXT")

    def _render_section_header(self, pdf: FPDF, title: str):
        """Render a section header."""
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.3)
        pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
        pdf.ln(5)

    def _render_html(self, result: ProcessedResult) -> str:
        """
        Render a ProcessedResult as HTML (for testing purposes).
        
        This provides HTML representation for test assertions.

        Args:
            result: The processed result to render.

        Returns:
            HTML string representation.
        """
        return self._render_batch_html([result])

    def _render_batch_html(self, results: List[ProcessedResult]) -> str:
        """
        Render multiple ProcessedResults as HTML (for testing purposes).

        Args:
            results: List of processed results to render.

        Returns:
            HTML string representation.
        """
        parts = []
        
        for result in results:
            parts.append(f"<article>")
            
            # Title
            title = result.content.title if result.content and result.content.title else "Untitled"
            parts.append(f"<h2>{self._escape(title)}</h2>")
            
            # Topics
            if result.summary and result.summary.topics:
                for topic in result.summary.topics:
                    parts.append(f'<span class="topic">{self._escape(topic)}</span>')
            
            # Metadata
            if result.content:
                if result.content.author:
                    parts.append(f"<span>Author: {self._escape(result.content.author)}</span>")
                if result.content.site_name:
                    parts.append(f"<span>Site: {self._escape(result.content.site_name)}</span>")
            
            # Error handling
            if result.status == ProcessingStatus.FAILED:
                parts.append(f"<div class='error'>Failed: {self._escape(result.error or 'Error')}</div>")
            
            # Summary
            if result.summary:
                # Executive summary
                parts.append("<section class='executive-summary'>")
                parts.append("<h3>Executive Summary</h3>")
                parts.append(f"<p>{self._escape(result.summary.executive_summary)}</p>")
                
                # Sentiment
                sentiment = result.summary.sentiment
                parts.append(f"<span class='sentiment {sentiment.value}'>{sentiment.value}</span>")
                parts.append("</section>")
                
                # Key points
                parts.append("<section class='key-points'>")
                parts.append("<h3>Key Points</h3>")
                for point in result.summary.key_points:
                    parts.append(f"<li>{self._escape(point)}</li>")
                parts.append("</section>")
                
                # Entities
                if result.summary.entities:
                    parts.append("<section class='entities'>")
                    for entity in result.summary.entities:
                        entity_type = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)
                        parts.append(f"<span class='entity {entity_type.lower()}'>{self._escape(entity.text)}</span>")
                    parts.append("</section>")
                
                # Footnotes
                if result.summary.footnotes:
                    parts.append("<section class='footnotes'>")
                    for fn in result.summary.footnotes:
                        parts.append(f"<blockquote>{self._escape(fn.source_text)}</blockquote>")
                        parts.append(f"<p>{self._escape(fn.context)}</p>")
                    parts.append("</section>")
            
            # Fact check
            if result.fact_check:
                fc = result.fact_check
                parts.append("<section class='fact-check'>")
                parts.append("<h3>Fact-Check Results</h3>")
                
                for claim in fc.verified_claims:
                    rating = claim.rating.value
                    parts.append(f"<div class='claim rating-{rating}'>{self._escape(claim.claim)}</div>")
                    parts.append(f"<span class='rating'>{rating}</span>")
                    parts.append(f"<span class='source'>{self._escape(claim.source)}</span>")
                
                if fc.publisher_credibility:
                    cred = fc.publisher_credibility
                    if cred.score is not None:
                        parts.append(f"<span class='credibility-score'>{cred.score}</span>")
                    parts.append(f"<span class='credibility-source'>{self._escape(cred.source)}</span>")
                
                parts.append("</section>")
            
            parts.append("</article>")
        
        return "\n".join(parts)

    def _escape(self, text: Optional[str]) -> str:
        """HTML escape text safely."""
        if text is None:
            return ""
        return html_module.escape(str(text))
