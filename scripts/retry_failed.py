#!/usr/bin/env python3
"""
Retry failed URLs from batch_results_test.json and regenerate deliverables.

This script:
1. Loads failed results from batch_results_test.json
2. Retries only the 13 high-priority URLs (skipping duplicates)
3. Merges successful retries back into the JSON
4. Regenerates all deliverables (PDF report, prep doc, slides)
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import NewsAgent
from src.export.pdf_report import PDFReportGenerator
from src.export.prep_document import PrepDocumentGenerator
from src.export.slides_deck import SlidesDeckGenerator
from src.export.utils import sanitize_text
from src.models.schemas import ProcessedResult, ProcessingStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# URLs to retry (13 high-priority, non-duplicate)
URLS_TO_RETRY = [
    "https://cloud.google.com/blog/products/ai-machine-learning/gemini-3-flash-for-enterprises",
    "https://developers.googleblog.com/gemini-3-flash-is-now-available-in-gemini-cli",
    "https://blog.google/technology/developers/gemini-3-pro-vision",
    "https://openai.com/index/introducing-gpt-5-2-codex",
    "https://openai.com/index/gpt-5-system-card-update-gpt-5-2",
    "https://arcprize.org/blog/arc-prize-2025-results-analysis",
    "https://techfundingnews.com/2b-raised-ranking-the-biggest-uk-ai-deals-in-2025",
    "https://www.mobihealthnews.com/news/isomorphic-labs-secures-600m-funding-ai-drug-design",
    "https://www.datacenterknowledge.com/investing/uk-s-nscale-to-boost-us-footprint-with-865m-nc-data-center-deal",
    "https://www.investing.com/news/stock-market-news/nvidia-to-acquire-groq-for-20-billion-in-its-largest-deal-ever-cnbc-reports-4422745",
    "https://www.foxnews.com/tech/chatgpts-gpt-5-2-here-feels-rushed",
    "https://mlq.ai/news/meta-readies-nextgeneration-mango-and-avocado-ai-models-for-2026-launch",
    "https://timesofindia.indiatimes.com/technology/tech-news/ai-layoffs-in-2025-crossed-50000-4-biggest-technology-companies-that-called-out-ai-in-their-job-cuts-announcement-and-how/articleshow/126106779.cms",
]

# URLs to skip (duplicates or broken)
URLS_TO_SKIP = [
    "https://www.ubergizmo.com/2025/12/meta-plans-new-visual-ai-model",  # duplicate of WSJ
    "https://timesofindia.indiatimes.com/technology/tech-news/how-google-fear-and-threat-just-made-nvidia-just-spend-20-billion/articleshow/126188810.cms",  # duplicate
    "https://www.calcalistech.com/ctechnews/article/hjyziyc7wl",  # duplicate
    "https://www.techspot.com/news/110674-nvidia-sk-hynix-building-ai-ssd-could-10x.html",  # duplicate
    "https://overclock3d.net/news/storage/first-dram-now-nand-nvidia-and-sk-hynix-target-nand-with-ai-ssd-plans",  # duplicate
    "https://forums.developer.nvidia.com/t/nvidia-grandmasters-win-the-arc-prize-2025-competition/353690",  # duplicate
    "https://openai.com/index/accelerating-biological-research-in-the-wet-lab",  # client-side error
]

BATCH_RESULTS_PATH = Path(__file__).parent.parent / "batch_results_test.json"
DELIVERABLES_PATH = Path(__file__).parent.parent / "deliverables"


async def retry_urls(urls: list[str]) -> list[ProcessedResult]:
    """Retry processing for a list of URLs with rate limiting."""
    agent = NewsAgent()
    results = []
    
    try:
        for i, url in enumerate(urls):
            logger.info(f"Processing {i+1}/{len(urls)}: {url}")
            try:
                result = await agent.process(url, skip_fact_check=True)
                results.append(result)
                
                if result.status == ProcessingStatus.COMPLETED:
                    logger.info(f"  ✓ Success: {result.content.title[:50] if result.content else 'No title'}...")
                else:
                    logger.warning(f"  ✗ Failed: {result.error}")
                    
            except Exception as e:
                logger.error(f"  ✗ Error processing {url}: {e}")
                # Create a failed result
                result = ProcessedResult(
                    url=url,
                    status=ProcessingStatus.FAILED,
                    error=str(e)
                )
                results.append(result)
            
            # Rate limiting: wait 15 seconds between requests (4 RPM to be safe)
            if i < len(urls) - 1:
                logger.info("  Waiting 15s for rate limit...")
                await asyncio.sleep(15)
                
    finally:
        await agent.close()
    
    return results


def load_batch_results() -> list[dict]:
    """Load existing batch results from JSON."""
    with open(BATCH_RESULTS_PATH, "r") as f:
        return json.load(f)


def save_batch_results(results: list[dict]):
    """Save batch results to JSON."""
    with open(BATCH_RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)


def merge_results(original: list[dict], retried: list[ProcessedResult]) -> list[dict]:
    """Merge retried results into original, replacing by URL."""
    # Create a map of URL -> new result
    retry_map = {r.url: r.model_dump() for r in retried if r.status == ProcessingStatus.COMPLETED}
    
    merged = []
    for item in original:
        url = item["url"]
        if url in retry_map:
            logger.info(f"Replacing result for: {url}")
            merged.append(retry_map[url])
        else:
            merged.append(item)
    
    return merged


def regenerate_deliverables(results: list[dict]):
    """Regenerate all deliverable files from results."""
    # Sanitize text to handle Unicode characters that PDFs can't render
    sanitized_results = sanitize_text(results)
    
    # Convert dicts to ProcessedResult objects
    processed_results = []
    for r in sanitized_results:
        try:
            pr = ProcessedResult.model_validate(r)
            processed_results.append(pr)
        except Exception as e:
            logger.warning(f"Could not parse result for {r.get('url', 'unknown')}: {e}")
    
    logger.info(f"Regenerating deliverables with {len(processed_results)} results...")
    
    # 1. Regenerate batch report PDF
    try:
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_batch(processed_results)
        pdf_path = DELIVERABLES_PATH / "batch_report_test_12_27_25.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"  ✓ Generated: {pdf_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed to generate batch report: {e}")
    
    # 2. Regenerate prep document PDF
    try:
        prep_gen = PrepDocumentGenerator()
        prep_bytes = prep_gen.generate(processed_results)
        prep_path = DELIVERABLES_PATH / "prep_document_test_12_27_25.pdf"
        with open(prep_path, "wb") as f:
            f.write(prep_bytes)
        logger.info(f"  ✓ Generated: {prep_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed to generate prep document: {e}")
    
    # 3. Regenerate slides deck
    try:
        slides_gen = SlidesDeckGenerator()
        slides_md = slides_gen.generate(processed_results)
        slides_path = DELIVERABLES_PATH / "slides_deck_test_12_27_25.md"
        with open(slides_path, "w") as f:
            f.write(slides_md)
        logger.info(f"  ✓ Generated: {slides_path.name}")
    except Exception as e:
        logger.error(f"  ✗ Failed to generate slides deck: {e}")


async def main():
    """Main execution flow."""
    logger.info("=" * 60)
    logger.info("Retry Failed URLs Script")
    logger.info("=" * 60)
    
    # Step 1: Load existing results
    logger.info("\n[Step 1] Loading existing batch results...")
    original_results = load_batch_results()
    
    # Count current status
    completed = sum(1 for r in original_results if r.get("status") == "completed")
    failed = sum(1 for r in original_results if r.get("status") == "failed")
    logger.info(f"  Current: {completed} completed, {failed} failed")
    
    # Step 2: Retry selected URLs
    logger.info(f"\n[Step 2] Retrying {len(URLS_TO_RETRY)} high-priority URLs...")
    logger.info(f"  (Skipping {len(URLS_TO_SKIP)} duplicate/broken URLs)")
    
    retried_results = await retry_urls(URLS_TO_RETRY)
    
    # Count retry results
    retry_success = sum(1 for r in retried_results if r.status == ProcessingStatus.COMPLETED)
    retry_failed = sum(1 for r in retried_results if r.status == ProcessingStatus.FAILED)
    logger.info(f"\n  Retry results: {retry_success} succeeded, {retry_failed} failed")
    
    # Step 3: Merge results
    logger.info("\n[Step 3] Merging results...")
    merged_results = merge_results(original_results, retried_results)
    
    # Count final status
    final_completed = sum(1 for r in merged_results if r.get("status") == "completed")
    final_failed = sum(1 for r in merged_results if r.get("status") == "failed")
    logger.info(f"  Final: {final_completed} completed, {final_failed} failed")
    
    # Step 4: Save merged results
    logger.info("\n[Step 4] Saving merged results to batch_results_test.json...")
    save_batch_results(merged_results)
    logger.info("  ✓ Saved")
    
    # Step 5: Regenerate deliverables
    logger.info("\n[Step 5] Regenerating deliverables...")
    regenerate_deliverables(merged_results)
    
    logger.info("\n" + "=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

