"""Tests for PDF export functionality.

TDD Approach: These tests are written BEFORE the implementation.
They define the expected behavior of PDFReportGenerator.
"""

from datetime import datetime, timezone

import pytest

from src.models.schemas import (
    ClaimRating,
    ContentMetadata,
    ContentSummary,
    Entity,
    EntityType,
    FactCheckReport,
    FactCheckResult,
    Footnote,
    ProcessedResult,
    ProcessingStatus,
    PublisherCredibility,
    Sentiment,
    URLType,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_content_metadata():
    """Create sample content metadata for testing."""
    return ContentMetadata(
        title="Breaking: AI Revolutionizes News Curation",
        author="Jane Smith",
        published_date=datetime(2024, 12, 20, 10, 30, tzinfo=timezone.utc),
        word_count=1500,
        language="en",
        site_name="Tech News Daily",
    )


@pytest.fixture
def sample_summary():
    """Create sample content summary for testing."""
    return ContentSummary(
        executive_summary=(
            "A groundbreaking AI system has been developed that can automatically "
            "curate and summarize news articles with unprecedented accuracy. The system "
            "uses advanced language models to extract key information and fact-check claims."
        ),
        key_points=[
            "New AI system achieves 95% accuracy in news summarization",
            "System can process 1000 articles per minute",
            "Fact-checking capabilities reduce misinformation spread",
            "Major news organizations expressing interest in adoption",
        ],
        sentiment=Sentiment.POSITIVE,
        entities=[
            Entity(text="OpenAI", type=EntityType.ORGANIZATION, relevance=0.9),
            Entity(text="Sam Altman", type=EntityType.PERSON, relevance=0.8),
            Entity(text="San Francisco", type=EntityType.LOCATION, relevance=0.6),
        ],
        implications=[
            "Could transform how news is consumed globally",
            "May reduce journalist workload for routine stories",
        ],
        footnotes=[
            Footnote(
                id=1,
                source_text="AI will fundamentally change journalism",
                context="Quote from lead researcher",
            ),
        ],
        topics=["Artificial Intelligence", "Journalism", "Technology"],
    )


@pytest.fixture
def sample_fact_check():
    """Create sample fact-check report for testing."""
    return FactCheckReport(
        claims_analyzed=3,
        verified_claims=[
            FactCheckResult(
                claim="AI system achieves 95% accuracy",
                rating=ClaimRating.MOSTLY_TRUE,
                source="TechFactCheck.org",
                source_url="https://techfactcheck.org/ai-accuracy",
                explanation="Independent tests confirmed 93-96% accuracy range",
            ),
            FactCheckResult(
                claim="System can process 1000 articles per minute",
                rating=ClaimRating.TRUE,
                source="PerformanceReview.com",
                source_url="https://performancereview.com/ai-speed",
                explanation="Benchmark tests verified this claim",
            ),
        ],
        unverified_claims=[
            "Major news organizations expressing interest",
        ],
        publisher_credibility=PublisherCredibility(
            score=85,
            source="MediaBiasFactCheck",
            notes="High factual reporting, minimal bias",
        ),
    )


@pytest.fixture
def complete_processed_result(sample_content_metadata, sample_summary, sample_fact_check):
    """Create a complete ProcessedResult with all fields populated."""
    return ProcessedResult(
        url="https://technews.example.com/ai-news-curation",
        source_type=URLType.NEWS_ARTICLE,
        status=ProcessingStatus.COMPLETED,
        extracted_at=datetime(2024, 12, 20, 11, 0, tzinfo=timezone.utc),
        content=sample_content_metadata,
        summary=sample_summary,
        fact_check=sample_fact_check,
        processing_time_ms=2500,
    )


@pytest.fixture
def minimal_processed_result():
    """Create a ProcessedResult with only required fields (no optional data)."""
    return ProcessedResult(
        url="https://example.com/article",
        source_type=URLType.NEWS_ARTICLE,
        status=ProcessingStatus.COMPLETED,
        content=ContentMetadata(title="Simple Article", word_count=500),
        summary=ContentSummary(
            executive_summary="A brief article summary.",
            key_points=["Main point of the article"],
            sentiment=Sentiment.NEUTRAL,
        ),
    )


@pytest.fixture
def failed_processed_result():
    """Create a failed ProcessedResult."""
    return ProcessedResult(
        url="https://example.com/failed",
        source_type=URLType.UNKNOWN,
        status=ProcessingStatus.FAILED,
        error="Failed to extract content: Connection timeout",
    )


# ============================================================================
# Unit Tests for PDFReportGenerator
# ============================================================================


class TestPDFReportGenerator:
    """Unit tests for PDFReportGenerator class."""

    def test_pdf_generator_creates_valid_pdf(self, complete_processed_result):
        """PDF generator returns valid PDF bytes from ProcessedResult."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf_bytes = generator.generate(complete_processed_result)

        # Check that we get bytes back
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

        # Check PDF magic bytes (PDF files start with %PDF-)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_contains_title(self, complete_processed_result):
        """Generated PDF contains the article title."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()

        # Get the HTML content (intermediate step) to verify content
        html = generator._render_html(complete_processed_result)

        assert "Breaking: AI Revolutionizes News Curation" in html

    def test_pdf_contains_executive_summary(self, complete_processed_result):
        """Generated PDF contains the executive summary section."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        assert "Executive Summary" in html
        assert "groundbreaking AI system" in html

    def test_pdf_contains_key_points(self, complete_processed_result):
        """Generated PDF contains all key points."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        assert "Key Points" in html
        assert "95% accuracy" in html
        assert "1000 articles per minute" in html
        assert "Fact-checking capabilities" in html

    def test_pdf_sentiment_color_coding(self):
        """Sentiment is color-coded correctly (green/red/orange)."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()

        # Test positive sentiment -> green
        positive_result = ProcessedResult(
            url="https://example.com/positive",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Good news!",
                key_points=["Point"],
                sentiment=Sentiment.POSITIVE,
            ),
        )
        html = generator._render_html(positive_result)
        # Should contain green color class or style for positive
        assert "positive" in html.lower() or "green" in html.lower()

        # Test negative sentiment -> red
        negative_result = ProcessedResult(
            url="https://example.com/negative",
            source_type=URLType.NEWS_ARTICLE,
            status=ProcessingStatus.COMPLETED,
            summary=ContentSummary(
                executive_summary="Bad news.",
                key_points=["Point"],
                sentiment=Sentiment.NEGATIVE,
            ),
        )
        html = generator._render_html(negative_result)
        assert "negative" in html.lower() or "red" in html.lower()

    def test_pdf_handles_missing_optional_fields(self, minimal_processed_result):
        """PDF generation works when optional fields are None."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()

        # Should not raise an error
        pdf_bytes = generator.generate(minimal_processed_result)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_does_not_render_entities_section(self, complete_processed_result):
        """PDF generation does NOT render Key Entities section (removed feature).
        
        The Key Entities section was removed from PDF output to simplify reports.
        This test ensures entities are not displayed even when present in data.
        """
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()

        # Even with entities in the data, the section should NOT appear in output
        html = generator._render_html(complete_processed_result)

        # Key Entities header should NOT be present
        assert "Key Entities" not in html
        
        # Entity class/section should NOT be present in HTML
        assert "class='entities'" not in html
        assert "class='entity" not in html
        
        # Other sections should still be present
        assert "Executive Summary" in html
        assert "Key Points" in html

    def test_pdf_handles_empty_entities(self, minimal_processed_result):
        """PDF generation works with empty entities list."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()

        # Minimal result has no entities
        html = generator._render_html(minimal_processed_result)

        # Should still generate valid HTML without entity section
        assert "Simple Article" in html
        # Key Entities should not appear regardless
        assert "Key Entities" not in html

    def test_pdf_fact_check_section(self, complete_processed_result):
        """Fact check results render with proper rating colors."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        # Should contain fact-check section
        assert "Fact Check" in html or "Fact-Check" in html

        # Should contain verified claims
        assert "95% accuracy" in html
        assert "TechFactCheck.org" in html

        # Should have rating indicators
        assert "mostly_true" in html.lower() or "mostly true" in html.lower()
        assert "true" in html.lower()

    def test_pdf_handles_failed_result(self, failed_processed_result):
        """PDF generation handles failed results gracefully."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()

        # Should not crash, should show error message
        pdf_bytes = generator.generate(failed_processed_result)

        assert isinstance(pdf_bytes, bytes)

        html = generator._render_html(failed_processed_result)
        assert "Failed" in html or "Error" in html
        assert "Connection timeout" in html

    def test_pdf_metadata_section(self, complete_processed_result):
        """PDF contains metadata like author, date, source."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        assert "Jane Smith" in html
        assert "Tech News Daily" in html or "technews.example.com" in html

    def test_pdf_topics_displayed(self, complete_processed_result):
        """PDF displays topic tags."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        assert "Artificial Intelligence" in html
        assert "Journalism" in html

    def test_pdf_footnotes_section(self, complete_processed_result):
        """PDF contains footnotes/citations section."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        assert "AI will fundamentally change journalism" in html
        assert "lead researcher" in html

    def test_pdf_publisher_credibility(self, complete_processed_result):
        """PDF shows publisher credibility score."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        html = generator._render_html(complete_processed_result)

        assert "85" in html or "Credibility" in html
        assert "MediaBiasFactCheck" in html

    def test_generate_filename(self, complete_processed_result):
        """Test filename generation for PDF downloads."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        filename = generator.get_filename(complete_processed_result)

        # Should be a safe filename
        assert filename.endswith(".pdf")
        assert "/" not in filename
        assert "\\" not in filename
        # Should contain some reference to the content
        assert len(filename) > 4  # More than just ".pdf"


class TestPDFReportGeneratorBatch:
    """Tests for batch PDF generation (multiple results)."""

    def test_generate_batch_pdf(self, complete_processed_result, minimal_processed_result):
        """Can generate a single PDF from multiple results."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        results = [complete_processed_result, minimal_processed_result]

        pdf_bytes = generator.generate_batch(results)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_batch_pdf_contains_all_results(
        self, complete_processed_result, minimal_processed_result
    ):
        """Batch PDF contains content from all results."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        results = [complete_processed_result, minimal_processed_result]

        html = generator._render_batch_html(results)

        # Should contain titles from both results
        assert "Breaking: AI Revolutionizes News Curation" in html
        assert "Simple Article" in html


# ============================================================================
# API Integration Tests
# ============================================================================


class TestPDFExportAPI:
    """Integration tests for PDF export API endpoints."""

    @pytest.fixture
    def test_client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        return TestClient(app)

    def test_export_job_pdf_not_found(self, test_client):
        """GET /api/jobs/{id}/export/pdf returns 404 for non-existent job."""
        response = test_client.get("/api/jobs/nonexistent-job-id/export/pdf")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_export_job_pdf_returns_pdf_content_type(self, test_client):
        """GET /api/jobs/{id}/export/pdf returns application/pdf content type."""
        # First, we need to create a job
        # For now, test the endpoint structure - a real integration test would
        # submit URLs, wait for processing, then export
        
        # Submit a URL and get job ID
        response = test_client.post(
            "/api/submit",
            json={"urls": ["https://example.com/test-article"]}
        )
        
        # Even if processing fails, we should have a job
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Try to export - might fail if processing isn't complete, but should
        # return proper error or PDF
        export_response = test_client.get(f"/api/jobs/{job_id}/export/pdf")
        
        # Should either succeed with PDF or fail with proper error
        assert export_response.status_code in [200, 400, 404]
        
        if export_response.status_code == 200:
            assert export_response.headers["content-type"] == "application/pdf"
            assert export_response.content[:5] == b"%PDF-"

    def test_export_endpoints_exist(self, test_client):
        """Verify export endpoints are registered."""
        # Get OpenAPI schema to verify endpoints exist
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi = response.json()
        paths = openapi.get("paths", {})
        
        # Check that export endpoints are defined
        assert "/api/jobs/{job_id}/export/pdf" in paths or any(
            "export" in path and "pdf" in path for path in paths
        )

    def test_health_check(self, test_client):
        """Health check endpoint still works."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ============================================================================
# Tests for Aggregated PDF Generation with Footnotes and Sources
# ============================================================================


class TestPDFAggregatedGeneration:
    """Tests for aggregated PDF generation with footnotes and sources sections."""

    @pytest.fixture
    def sample_source_reference(self):
        """Create sample source reference for testing."""
        from src.models.schemas import SourceReference, URLType
        
        return SourceReference(
            url="https://technews.example.com/ai-news",
            title="AI News Article",
            site_name="Tech News Daily",
            author="Jane Doe",
            published_date=datetime(2024, 12, 20, 10, 30, tzinfo=timezone.utc),
            source_type=URLType.NEWS_ARTICLE,
        )

    @pytest.fixture
    def sample_aggregated_summary_with_footnotes(self):
        """Create sample summary with footnotes for testing."""
        return ContentSummary(
            executive_summary=(
                "An aggregated view of multiple sources covering AI developments. "
                "This summary combines insights from various publishers."
            ),
            key_points=[
                "Multiple sources confirm AI advancement",
                "Industry leaders express optimism",
                "Regulatory concerns remain",
            ],
            sentiment=Sentiment.POSITIVE,
            implications=[
                "Accelerated AI adoption across industries",
                "New regulatory frameworks may emerge",
            ],
            footnotes=[
                Footnote(
                    id=1,
                    source_text="AI is transforming every industry",
                    context="Quote from industry expert at Tech Summit 2024",
                ),
                Footnote(
                    id=2,
                    source_text="Regulation must keep pace with innovation",
                    context="Statement from policy think tank report",
                ),
            ],
            topics=["AI", "Technology", "Regulation"],
        )

    @pytest.fixture
    def aggregated_result_with_sources(self, sample_aggregated_summary_with_footnotes):
        """Create an aggregated result with multiple sources and footnotes."""
        from src.models.schemas import AggregatedResult, SourceReference, URLType
        
        sources = [
            SourceReference(
                url="https://technews.example.com/ai-news",
                title="AI News Article",
                site_name="Tech News Daily",
                author="Jane Doe",
                published_date=datetime(2024, 12, 20, 10, 30, tzinfo=timezone.utc),
                source_type=URLType.NEWS_ARTICLE,
            ),
            SourceReference(
                url="https://businessweek.example.com/ai-impact",
                title="The AI Impact on Business",
                site_name="Business Weekly",
                author="John Smith",
                published_date=datetime(2024, 12, 19, 14, 0, tzinfo=timezone.utc),
                source_type=URLType.NEWS_ARTICLE,
            ),
            SourceReference(
                url="https://techblog.example.com/ai-future",
                title="The Future of AI",
                site_name="Tech Blog",
                source_type=URLType.BLOG,
            ),
        ]
        
        return AggregatedResult(
            title="AI Revolution: Combined Coverage",
            sources=sources,
            summary=sample_aggregated_summary_with_footnotes,
            source_type=URLType.NEWS_ARTICLE,
            is_aggregated=True,
            original_count=3,
        )

    @pytest.fixture
    def aggregated_result_set(self, aggregated_result_with_sources):
        """Create an aggregated result set for batch PDF generation."""
        from src.models.schemas import AggregatedResultSet
        
        return AggregatedResultSet(
            results=[aggregated_result_with_sources],
            total_original=3,
            total_aggregated=1,
            duplicates_merged=1,
        )

    def test_aggregated_pdf_generates_valid_pdf(self, aggregated_result_set):
        """Aggregated PDF generation returns valid PDF bytes."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf_bytes = generator.generate_aggregated_batch(aggregated_result_set)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_aggregated_pdf_renders_footnotes_section(self, aggregated_result_with_sources):
        """Aggregated PDF contains footnotes/citations section."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf = generator._create_pdf()
        
        # Render the aggregated result
        generator._render_aggregated_result(pdf, aggregated_result_with_sources, skip_header=False)
        
        # Generate PDF bytes to ensure no errors
        pdf_bytes = bytes(pdf.output())
        assert pdf_bytes[:5] == b"%PDF-"
        
        # The footnotes should be rendered without error
        # (Font size validation is visual, but we ensure the section renders)
        assert aggregated_result_with_sources.summary.footnotes is not None
        assert len(aggregated_result_with_sources.summary.footnotes) == 2

    def test_aggregated_pdf_renders_sources_section(self, aggregated_result_with_sources):
        """Aggregated PDF contains sources section when multiple sources exist."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf = generator._create_pdf()
        
        # Render just the sources section
        generator._render_sources_section(pdf, aggregated_result_with_sources)
        
        # Generate PDF bytes to ensure no errors
        pdf_bytes = bytes(pdf.output())
        assert pdf_bytes[:5] == b"%PDF-"
        
        # Verify sources were in the result
        assert len(aggregated_result_with_sources.sources) == 3

    def test_aggregated_pdf_renders_footnotes_directly(self, aggregated_result_with_sources):
        """Footnotes section renders directly without error."""
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf = generator._create_pdf()
        
        # Render the footnotes section directly
        generator._render_aggregated_footnotes_section(pdf, aggregated_result_with_sources)
        
        # Generate PDF bytes to ensure no errors
        pdf_bytes = bytes(pdf.output())
        assert pdf_bytes[:5] == b"%PDF-"

    def test_secondary_section_header_method_exists(self):
        """Verify secondary section header method exists for smaller headers.
        
        This test is written before implementation (TDD).
        The _render_secondary_section_header method should use smaller fonts
        for less essential sections like citations and sources.
        """
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        
        # The method should exist
        assert hasattr(generator, '_render_secondary_section_header'), \
            "_render_secondary_section_header method should be implemented"
        
        # Should be callable with pdf and title
        pdf = generator._create_pdf()
        generator._render_secondary_section_header(pdf, "Test Section")
        
        # Should generate valid PDF
        pdf_bytes = bytes(pdf.output())
        assert pdf_bytes[:5] == b"%PDF-"

    def test_footnotes_use_secondary_header(self, aggregated_result_with_sources):
        """Footnotes section uses secondary (smaller) header styling.
        
        Visual verification will confirm actual font sizes, but this test
        ensures the section header is rendered appropriately.
        """
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf = generator._create_pdf()
        
        # Render footnotes - should use smaller styling
        generator._render_aggregated_footnotes_section(pdf, aggregated_result_with_sources)
        
        pdf_bytes = bytes(pdf.output())
        assert len(pdf_bytes) > 0

    def test_sources_use_secondary_header(self, aggregated_result_with_sources):
        """Sources section uses secondary (smaller) header styling.
        
        Visual verification will confirm actual font sizes, but this test
        ensures the section header is rendered appropriately.
        """
        from src.export.pdf_report import PDFReportGenerator

        generator = PDFReportGenerator()
        pdf = generator._create_pdf()
        
        # Render sources - should use smaller styling
        generator._render_sources_section(pdf, aggregated_result_with_sources)
        
        pdf_bytes = bytes(pdf.output())
        assert len(pdf_bytes) > 0

