#!/usr/bin/env python3
"""
Regenerate all deliverables from existing batch_results_test.json.

This script performs deduplication/aggregation of similar articles using Gemini,
then regenerates the PDF reports and slides deck from the aggregated data.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aggregator.deduplicator import NewsAggregator, AggregationError
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


def load_results(path: Path) -> list:
    """Load and parse batch results from JSON file."""
    logger.info(f"Loading batch results from {path.name}...")
    with open(path, "r") as f:
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
    return processed_results


def aggregate_results(processed_results: list, perform_final_review: bool = True):
    """
    Run Gemini-powered deduplication/aggregation on the results.
    
    Returns:
        AggregatedResultSet with merged entries.
    """
    logger.info("\n" + "=" * 60)
    logger.info("Running Deduplication & Aggregation with Gemini")
    logger.info("=" * 60)
    
    try:
        aggregator = NewsAggregator()
        result_set = aggregator.aggregate(processed_results, perform_final_review=perform_final_review)
        
        logger.info(f"\nAggregation Results:")
        logger.info(f"  - Original articles: {result_set.total_original}")
        logger.info(f"  - Unique stories: {result_set.total_aggregated}")
        logger.info(f"  - Duplicates merged: {result_set.duplicates_merged}")
        
        return result_set
    except AggregationError as e:
        logger.error(f"Aggregation failed: {e}")
        raise


def save_aggregated_results(result_set, output_path: Path):
    """Save aggregated results to JSON file."""
    logger.info(f"\nSaving aggregated results to {output_path.name}...")
    
    # Convert to dict for JSON serialization
    data = {
        "total_original": result_set.total_original,
        "total_aggregated": result_set.total_aggregated,
        "duplicates_merged": result_set.duplicates_merged,
        "aggregated_at": result_set.aggregated_at.isoformat(),
        "results": [r.model_dump(mode="json") for r in result_set.results]
    }
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    
    logger.info(f"  ✓ Saved: {output_path.name}")


def sanitize_aggregated_results(result_set):
    """Sanitize text in aggregated results for PDF generation."""
    for result in result_set.results:
        # Sanitize title
        result.title = sanitize_text(result.title)
        
        # Sanitize summary fields
        if result.summary:
            result.summary.executive_summary = sanitize_text(result.summary.executive_summary)
            result.summary.key_points = [sanitize_text(p) for p in result.summary.key_points]
            result.summary.implications = [sanitize_text(i) for i in result.summary.implications]
            result.summary.topics = [sanitize_text(t) for t in result.summary.topics]
            
            for fn in result.summary.footnotes:
                fn.source_text = sanitize_text(fn.source_text)
                fn.context = sanitize_text(fn.context)
            
            for entity in result.summary.entities:
                entity.text = sanitize_text(entity.text)
        
        # Sanitize source titles
        for source in result.sources:
            if source.title:
                source.title = sanitize_text(source.title)
    
    return result_set


def generate_deliverables(result_set, output_dir: Path, timestamp: str):
    """Generate all deliverables from aggregated results."""
    logger.info("\n" + "=" * 60)
    logger.info("Generating Deliverables from Aggregated Data")
    logger.info("=" * 60)
    
    # Sanitize text for PDF compatibility
    result_set = sanitize_aggregated_results(result_set)
    
    # 1. Generate batch report PDF
    logger.info(f"\nGenerating batch_report_aggregated_{timestamp}.pdf...")
    try:
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_aggregated_batch(result_set)
        pdf_path = output_dir / f"batch_report_aggregated_{timestamp}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"  ✓ Generated: {pdf_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Generate prep document PDF
    logger.info(f"\nGenerating prep_document_aggregated_{timestamp}.pdf...")
    try:
        prep_gen = PrepDocumentGenerator()
        prep_bytes = prep_gen.generate_aggregated(result_set)
        prep_path = output_dir / f"prep_document_aggregated_{timestamp}.pdf"
        with open(prep_path, "wb") as f:
            f.write(prep_bytes)
        logger.info(f"  ✓ Generated: {prep_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Generate slides deck
    logger.info(f"\nGenerating slides_deck_aggregated_{timestamp}.md...")
    try:
        slides_gen = SlidesDeckGenerator()
        slides_md = slides_gen.generate_aggregated(result_set)
        slides_path = output_dir / f"slides_deck_aggregated_{timestamp}.md"
        with open(slides_path, "w") as f:
            f.write(slides_md)
        logger.info(f"  ✓ Generated: {slides_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()


def generate_legacy_deliverables(processed_results: list, output_dir: Path, timestamp: str):
    """Generate deliverables without aggregation (legacy mode)."""
    logger.info("\n" + "=" * 60)
    logger.info("Generating Deliverables (Legacy Mode - No Aggregation)")
    logger.info("=" * 60)
    
    # 1. Generate batch report PDF
    logger.info(f"\nGenerating batch_report_{timestamp}.pdf...")
    try:
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_batch(processed_results)
        pdf_path = output_dir / f"batch_report_{timestamp}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"  ✓ Generated: {pdf_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
    
    # 2. Generate prep document PDF
    logger.info(f"\nGenerating prep_document_{timestamp}.pdf...")
    try:
        prep_gen = PrepDocumentGenerator()
        prep_bytes = prep_gen.generate(processed_results)
        prep_path = output_dir / f"prep_document_{timestamp}.pdf"
        with open(prep_path, "wb") as f:
            f.write(prep_bytes)
        logger.info(f"  ✓ Generated: {prep_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
    
    # 3. Generate slides deck
    logger.info(f"\nGenerating slides_deck_{timestamp}.md...")
    try:
        slides_gen = SlidesDeckGenerator()
        slides_md = slides_gen.generate(processed_results)
        slides_path = output_dir / f"slides_deck_{timestamp}.md"
        with open(slides_path, "w") as f:
            f.write(slides_md)
        logger.info(f"  ✓ Generated: {slides_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")


def main():
    """Main entry point for regenerating deliverables."""
    parser = argparse.ArgumentParser(
        description="Regenerate deliverables with optional deduplication/aggregation"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=BATCH_RESULTS_PATH,
        help="Path to input batch results JSON file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DELIVERABLES_PATH,
        help="Path to output deliverables directory"
    )
    parser.add_argument(
        "--no-aggregate",
        action="store_true",
        help="Skip aggregation and generate deliverables from raw results"
    )
    parser.add_argument(
        "--no-final-review",
        action="store_true",
        help="Skip Gemini's final review pass on aggregated entries"
    )
    parser.add_argument(
        "--save-aggregated",
        action="store_true",
        help="Save aggregated results to a JSON file"
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%m_%d_%y")
    
    logger.info("=" * 60)
    logger.info("Regenerating Deliverables")
    logger.info("=" * 60)
    
    # Load results
    processed_results = load_results(args.input)
    
    if args.no_aggregate:
        # Legacy mode - no aggregation
        generate_legacy_deliverables(processed_results, args.output, timestamp)
    else:
        # Aggregation mode
        result_set = aggregate_results(
            processed_results, 
            perform_final_review=not args.no_final_review
        )
        
        # Optionally save aggregated results
        if args.save_aggregated:
            aggregated_path = args.output / f"aggregated_results_{timestamp}.json"
            save_aggregated_results(result_set, aggregated_path)
        
        # Generate deliverables
        generate_deliverables(result_set, args.output, timestamp)
    
    logger.info("\n" + "=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
