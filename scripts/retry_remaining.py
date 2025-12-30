#!/usr/bin/env python3
"""
Retry the remaining 6 URLs that were incorrectly skipped.

These URLs have unique content that should be included:
- Ubergizmo: Consumer tech perspective on Meta's Mango
- Times of India: "Google fear" angle on Nvidia/Groq
- Calcalistech: Israeli tech coverage of Nvidia/Groq
- TechSpot: Technical hardware details on AI SSD
- Overclock3D: Enthusiast perspective on AI SSD
- NVIDIA Forums: Story about NVIDIA team winning ARC Prize
"""

import asyncio
import json
import logging
import sys
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

# The 6 URLs that were incorrectly skipped
URLS_TO_PROCESS = [
    "https://www.ubergizmo.com/2025/12/meta-plans-new-visual-ai-model",
    "https://timesofindia.indiatimes.com/technology/tech-news/how-google-fear-and-threat-just-made-nvidia-just-spend-20-billion/articleshow/126188810.cms",
    "https://www.calcalistech.com/ctechnews/article/hjyziyc7wl",
    "https://www.techspot.com/news/110674-nvidia-sk-hynix-building-ai-ssd-could-10x.html",
    "https://overclock3d.net/news/storage/first-dram-now-nand-nvidia-and-sk-hynix-target-nand-with-ai-ssd-plans",
    "https://forums.developer.nvidia.com/t/nvidia-grandmasters-win-the-arc-prize-2025-competition/353690",
]

BATCH_RESULTS_PATH = Path(__file__).parent.parent / "batch_results_test.json"
DELIVERABLES_PATH = Path(__file__).parent.parent / "deliverables"


async def process_urls(urls: list[str]) -> list[ProcessedResult]:
    """Process URLs with rate limiting."""
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
                result = ProcessedResult(
                    url=url,
                    status=ProcessingStatus.FAILED,
                    error=str(e)
                )
                results.append(result)
            
            # Rate limiting: wait 15 seconds between requests
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


def merge_results(original: list[dict], new_results: list[ProcessedResult]) -> list[dict]:
    """Merge new results into original, replacing by URL."""
    # Create a map of URL -> new result
    new_map = {r.url: r.model_dump() for r in new_results if r.status == ProcessingStatus.COMPLETED}
    
    merged = []
    for item in original:
        url = item["url"]
        if url in new_map:
            logger.info(f"Replacing result for: {url}")
            merged.append(new_map[url])
        else:
            merged.append(item)
    
    return merged


def regenerate_deliverables(results: list[dict]):
    """Regenerate all deliverable files from results."""
    # Sanitize text to handle Unicode characters
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
    logger.info("Process Remaining 6 URLs")
    logger.info("=" * 60)
    
    # Step 1: Load existing results
    logger.info("\n[Step 1] Loading existing batch results...")
    original_results = load_batch_results()
    
    completed = sum(1 for r in original_results if r.get("status") == "completed")
    failed = sum(1 for r in original_results if r.get("status") == "failed")
    logger.info(f"  Current: {completed} completed, {failed} failed")
    
    # Step 2: Process remaining URLs
    logger.info(f"\n[Step 2] Processing {len(URLS_TO_PROCESS)} remaining URLs...")
    
    new_results = await process_urls(URLS_TO_PROCESS)
    
    success = sum(1 for r in new_results if r.status == ProcessingStatus.COMPLETED)
    fail = sum(1 for r in new_results if r.status == ProcessingStatus.FAILED)
    logger.info(f"\n  Results: {success} succeeded, {fail} failed")
    
    # Step 3: Merge results
    logger.info("\n[Step 3] Merging results...")
    merged_results = merge_results(original_results, new_results)
    
    final_completed = sum(1 for r in merged_results if r.get("status") == "completed")
    final_failed = sum(1 for r in merged_results if r.get("status") == "failed")
    logger.info(f"  Final: {final_completed} completed, {final_failed} failed")
    
    # Step 4: Save merged results
    logger.info("\n[Step 4] Saving merged results...")
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

