#!/usr/bin/env python3
"""
Regenerate all deliverables from existing batch_results_test.json.

This script regenerates the PDF reports and slides deck with the new hyperlink support.
"""

import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.export.pdf_report import PDFReportGenerator
from src.export.prep_document import PrepDocumentGenerator
from src.export.slides_deck import SlidesDeckGenerator
from src.export.utils import sanitize_text
from src.models.schemas import ProcessedResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

BATCH_RESULTS_PATH = Path(__file__).parent.parent / "batch_results_test.json"
DELIVERABLES_PATH = Path(__file__).parent.parent / "deliverables"


def main():
    """Regenerate all deliverables."""
    logger.info("=" * 60)
    logger.info("Regenerating Deliverables with Hyperlink Support")
    logger.info("=" * 60)
    
    # Load batch results
    logger.info("\nLoading batch results...")
    with open(BATCH_RESULTS_PATH, "r") as f:
        results = json.load(f)
    
    # Sanitize text for PDF generation
    sanitized_results = sanitize_text(results)
    
    # Convert to ProcessedResult objects
    processed_results = []
    for r in sanitized_results:
        try:
            pr = ProcessedResult.model_validate(r)
            processed_results.append(pr)
        except Exception as e:
            logger.warning(f"Could not parse result for {r.get('url', 'unknown')}: {e}")
    
    logger.info(f"Loaded {len(processed_results)} results")
    
    # 1. Regenerate batch report PDF
    logger.info("\nGenerating batch_report_test_12_27_25.pdf...")
    try:
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_batch(processed_results)
        pdf_path = DELIVERABLES_PATH / "batch_report_test_12_27_25.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"  ✓ Generated: {pdf_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
    
    # 2. Regenerate prep document PDF
    logger.info("\nGenerating prep_document_test_12_27_25.pdf...")
    try:
        prep_gen = PrepDocumentGenerator()
        prep_bytes = prep_gen.generate(processed_results)
        prep_path = DELIVERABLES_PATH / "prep_document_test_12_27_25.pdf"
        with open(prep_path, "wb") as f:
            f.write(prep_bytes)
        logger.info(f"  ✓ Generated: {prep_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
    
    # 3. Regenerate slides deck
    logger.info("\nGenerating slides_deck_test_12_27_25.md...")
    try:
        slides_gen = SlidesDeckGenerator()
        slides_md = slides_gen.generate(processed_results)
        slides_path = DELIVERABLES_PATH / "slides_deck_test_12_27_25.md"
        with open(slides_path, "w") as f:
            f.write(slides_md)
        logger.info(f"  ✓ Generated: {slides_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

