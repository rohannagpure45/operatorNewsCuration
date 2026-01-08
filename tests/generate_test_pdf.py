"""Script to generate test PDF for visual verification of font size changes."""

import json
import pytest
from src.export.pdf_report import PDFReportGenerator
from src.models.schemas import AggregatedResultSet


def test_generate_sample_pdf_for_verification():
    """Generate a sample PDF to verify font size changes visually."""
    # Load the aggregated results
    with open('deliverables/aggregated_results_01_07_26.json', 'r') as f:
        data = json.load(f)

    # Create the result set
    result_set = AggregatedResultSet(**data)

    # Generate the PDF
    generator = PDFReportGenerator()
    pdf_bytes = generator.generate_aggregated_batch(result_set)

    # Save to deliverables folder
    output_path = 'deliverables/test_font_size_reduction.pdf'
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)

    print(f'\n\nGenerated PDF: {output_path}')
    print(f'Size: {len(pdf_bytes)} bytes')
    print(f'Number of results: {len(result_set.results)}')
    print(f'Results with footnotes: {sum(1 for r in result_set.results if r.summary.footnotes)}')
    print(f'Results with multiple sources: {sum(1 for r in result_set.results if len(r.sources) > 1)}')
    
    assert len(pdf_bytes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
