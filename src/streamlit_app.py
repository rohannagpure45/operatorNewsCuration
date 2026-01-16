"""Streamlit frontend for the News Curation Automation."""

# Path setup for Streamlit Cloud deployment
# When running on Streamlit Cloud, the app is executed from the repo root
# but the src package may not be in the Python path
import sys
from pathlib import Path

# Add the repo root to Python path if not already present
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import asyncio
import json
import logging
from datetime import datetime

import streamlit as st

# Configure logging for server-side error tracking
logger = logging.getLogger(__name__)

from src.agent import NewsAgent
from src.cache.cache import BatchRun, CacheEntry, LocalCache
from src.export.pdf_report import PDFReportGenerator
from src.export.slides_deck import SlidesDeckGenerator
from src.models.schemas import ProcessedResult, ProcessingStatus, Sentiment, URLType


# Initialize cache singleton (cached across Streamlit reruns)
@st.cache_resource
def get_cache():
    """Get or create the local cache singleton."""
    return LocalCache()


# Page configuration
st.set_page_config(
    page_title="News Curation Automation",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stMetric, [data-testid="stMetric"], [data-testid="metric-container"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    [data-testid="stMetric"] > div {
        background-color: transparent !important;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .entity-tag {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        margin: 0.1rem;
        border-radius: 0.25rem;
        font-size: 0.85rem;
    }
    .entity-person { background-color: #e3f2fd; color: #1565c0; }
    .entity-org { background-color: #f3e5f5; color: #7b1fa2; }
    .entity-loc { background-color: #e8f5e9; color: #2e7d32; }
    .entity-date { background-color: #fff3e0; color: #ef6c00; }
    .entity-money { background-color: #e0f2f1; color: #00695c; }
</style>
""", unsafe_allow_html=True)

# Initialize session state for batch results persistence
if "batch_results" not in st.session_state:
    st.session_state.batch_results = None
if "batch_urls" not in st.session_state:
    st.session_state.batch_urls = None
if "restore_batch_id" not in st.session_state:
    st.session_state.restore_batch_id = None
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "single"


def get_sentiment_emoji(sentiment: Sentiment) -> str:
    """Get emoji for sentiment."""
    mapping = {
        Sentiment.POSITIVE: "😊",
        Sentiment.NEGATIVE: "😔",
        Sentiment.NEUTRAL: "😐",
        Sentiment.MIXED: "🤔",
    }
    return mapping.get(sentiment, "❓")


def get_sentiment_color(sentiment: Sentiment) -> str:
    """Get color for sentiment."""
    mapping = {
        Sentiment.POSITIVE: "green",
        Sentiment.NEGATIVE: "red",
        Sentiment.NEUTRAL: "gray",
        Sentiment.MIXED: "orange",
    }
    return mapping.get(sentiment, "gray")


def get_rating_color(rating_value: str) -> str:
    """Get color for fact-check rating."""
    rating_value = rating_value.lower().strip() if rating_value else ""
    if rating_value in ["true", "mostly_true"]:
        return "green"
    elif rating_value in ["false", "mostly_false"]:
        return "red"
    else:  # mixed, unverified, insufficient_data, etc.
        return "orange"


def run_async(coro):
    """Run async coroutine in sync context."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Fallback if event loop is already running (e.g., in Jupyter/IPython)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def process_url_async(url: str, skip_fact_check: bool = False, api_key: str = None):
    """Process a URL asynchronously."""
    agent = NewsAgent(gemini_api_key=api_key)
    try:
        result = await agent.process(url, skip_fact_check=skip_fact_check)
        return result
    finally:
        await agent.close()


async def process_batch_async(urls: list, skip_fact_check: bool = False, api_key: str = None):
    """Process multiple URLs asynchronously."""
    agent = NewsAgent(gemini_api_key=api_key)
    try:
        results = await agent.process_batch(urls, skip_fact_check=skip_fact_check)
        return results
    finally:
        await agent.close()


def display_result(result):
    """Display a single processing result."""
    if result.status == ProcessingStatus.FAILED:
        st.error(f"**Failed:** {result.error}")
        return

    # Content metadata
    if result.content:
        meta = result.content
        cols = st.columns([3, 1, 1])
        with cols[0]:
            if meta.title:
                st.markdown(f"### {meta.title}")
            if meta.author:
                st.caption(f"By {meta.author}")
        with cols[1]:
            if meta.published_date:
                st.metric("Published", meta.published_date.strftime("%Y-%m-%d"))
        with cols[2]:
            st.metric("Words", f"{meta.word_count:,}")

    # Summary
    if result.summary:
        summary = result.summary

        # Executive summary
        st.markdown("#### Executive Summary")
        st.info(summary.executive_summary)

        # Key points and sentiment side by side
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("#### Key Points")
            for point in summary.key_points:
                st.markdown(f"• {point}")

        with col2:
            # Sentiment
            st.markdown("#### Sentiment")
            emoji = get_sentiment_emoji(summary.sentiment)
            color = get_sentiment_color(summary.sentiment)
            st.markdown(
                f"<h2 style='color: {color};'>{emoji} {summary.sentiment.value.title()}</h2>",
                unsafe_allow_html=True,
            )

            # Topics
            if summary.topics:
                st.markdown("#### Topics")
                for topic in summary.topics:
                    st.markdown(f"`{topic}`")

        # Entities
        if summary.entities:
            st.markdown("#### Entities Mentioned")
            entity_cols = st.columns(4)
            for i, entity in enumerate(summary.entities):
                with entity_cols[i % 4]:
                    entity_type = entity.type.value if hasattr(entity.type, 'value') else entity.type
                    st.markdown(f"**{entity.text}** ({entity_type})")

        # Implications
        if summary.implications:
            st.markdown("#### Implications")
            for imp in summary.implications:
                st.markdown(f"→ {imp}")

        # Footnotes
        if summary.footnotes:
            with st.expander("📝 Footnotes & Citations"):
                for fn in summary.footnotes:
                    st.markdown(f"**[{fn.id}]** _{fn.source_text}_")
                    st.caption(fn.context)

    # Fact check results
    if result.fact_check:
        fc = result.fact_check
        st.markdown("---")
        st.markdown("#### Fact Check Results")

        fc_cols = st.columns(3)
        with fc_cols[0]:
            st.metric("Claims Analyzed", fc.claims_analyzed)
        with fc_cols[1]:
            st.metric("Verified", len(fc.verified_claims))
        with fc_cols[2]:
            st.metric("Unverified", len(fc.unverified_claims))

        if fc.verified_claims:
            with st.expander("✅ Verified Claims"):
                for claim in fc.verified_claims:
                    rating_color = get_rating_color(claim.rating.value)
                    st.markdown(f"**Claim:** {claim.claim}")
                    st.markdown(f"**Rating:** :{rating_color}[{claim.rating.value}]")
                    st.markdown(f"**Source:** [{claim.source}]({claim.source_url})" if claim.source_url else f"**Source:** {claim.source}")
                    if claim.explanation:
                        st.caption(claim.explanation)
                    st.markdown("---")

        if fc.unverified_claims:
            with st.expander("❓ Unverified Claims"):
                for claim in fc.unverified_claims:
                    st.markdown(f"• {claim}")

        if fc.publisher_credibility:
            st.markdown("**Publisher Credibility:**")
            score = fc.publisher_credibility.score
            if score is not None:
                st.progress(score / 100)
                st.caption(f"Score: {score}/100 (Source: {fc.publisher_credibility.source})")

    # Processing metadata
    with st.expander("🔧 Processing Details"):
        details_cols = st.columns(3)
        with details_cols[0]:
            st.markdown(f"**Source Type:** {result.source_type.value}")
        with details_cols[1]:
            if result.extracted_at:
                st.markdown(f"**Extracted:** {result.extracted_at.strftime('%H:%M:%S')}")
        with details_cols[2]:
            if result.processing_time_ms:
                st.markdown(f"**Processing Time:** {result.processing_time_ms}ms")


def display_batch_results(results: list, show_clear_button: bool = True):
    """Display batch processing results with download buttons.
    
    Args:
        results: List of ProcessedResult objects to display
        show_clear_button: Whether to show the clear results button
    """
    if not results:
        return
    
    # Calculate stats
    completed_count = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
    failed_count = len(results) - completed_count
    
    # Header with clear button
    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown("### Results")
    with header_cols[1]:
        if show_clear_button:
            if st.button("🗑️ Clear Results", key="clear_batch_results"):
                st.session_state.batch_results = None
                st.session_state.batch_urls = None
                st.rerun()
    
    # Summary stats
    summary_cols = st.columns(3)
    with summary_cols[0]:
        st.metric("Total Processed", len(results))
    with summary_cols[1]:
        if len(results) > 0:
            st.metric("Successful", completed_count, delta=f"{(completed_count/len(results)*100):.0f}%")
        else:
            st.metric("Successful", 0)
    with summary_cols[2]:
        st.metric("Failed", failed_count)

    # Export all results - show above individual results for easy access
    st.markdown("---")
    st.markdown("#### 📦 Download All Deliverables")
    export_cols = st.columns(3)
    
    with export_cols[0]:
        # Generate PDF Report
        try:
            pdf_generator = PDFReportGenerator()
            pdf_bytes = pdf_generator.generate_batch(results)
            st.download_button(
                "📄 Download Report (PDF)",
                data=pdf_bytes,
                file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                key="batch_pdf_download",
            )
        except Exception as pdf_error:
            logger.exception("Error generating PDF report")
            st.warning("PDF report unavailable")
    
    with export_cols[1]:
        # Generate Slides Deck
        try:
            slides_generator = SlidesDeckGenerator()
            slides_md = slides_generator.generate(results)
            st.download_button(
                "📊 Download Slides (MD)",
                data=slides_md,
                file_name=f"slides_deck_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                key="batch_slides_download",
            )
        except Exception as slides_error:
            logger.exception("Error generating slides deck")
            st.warning("Slides deck unavailable")
    
    with export_cols[2]:
        # JSON export (for debugging/advanced use)
        all_results_json = json.dumps(
            [r.model_dump() for r in results],
            indent=2,
            default=str,
        )
        st.download_button(
            "📥 Download Raw (JSON)",
            data=all_results_json,
            file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="batch_json_download",
        )
    
    # Individual results - in collapsible sections below downloads
    st.markdown("---")
    st.markdown("#### 📋 Individual Results")
    for i, result in enumerate(results):
        status_icon = "✅" if result.status == ProcessingStatus.COMPLETED else "❌"
        with st.expander(f"{status_icon} Result {i+1}: {result.url[:60]}...", expanded=False):
            display_result(result)

def main():
    """Main Streamlit application."""
    # Sidebar
    with st.sidebar:
        st.title("📰 News Curation Automation")
        st.markdown("---")

        # Configuration
        st.markdown("### Settings")
        skip_fact_check = st.checkbox("Skip Fact-Checking", value=False, help="Skip the fact-checking step for faster processing")

        st.markdown("---")

        # Recents section - load BATCH RUNS from persistent cache
        cache = get_cache()
        recent_batches = cache.get_recent_batches(limit=10)

        if recent_batches:
            st.markdown("### 🕒 Recents")
            for i, batch in enumerate(recent_batches):
                status_icon = "✅" if batch.failed_count == 0 else "⚠️"
                time_str = batch.timestamp.strftime("%m/%d %H:%M")
                label = f"{status_icon} {batch.url_count} URLs - {time_str}"
                if st.button(label, key=f"recent_batch_{i}"):
                    st.session_state.restore_batch_id = batch.id
                    st.session_state.active_tab = "batch"
                    st.rerun()

        st.markdown("---")
        st.caption("Built with Trafilatura, Gemini, and Playwright")

    # Main content
    st.title("News Curation Automation")
    st.markdown("Extract, fact-check, and summarize content from news articles, Twitter/X, and SEC filings.")

    # API Key Handling
    from src.config import get_settings
    settings = get_settings()
    api_key = settings.gemini_api_key

    # If no API key in settings, ask for it in the sidebar
    if not api_key:
        with st.sidebar:
            st.markdown("### 🔑 API Key Required")
            st.info("No Gemini API key found in implementation settings. Please enter it below.")
            api_key = st.text_input("Gemini API Key", type="password", help="Get one at https://aistudio.google.com/app/apikey")
            if not api_key:
                st.warning("Please enter your API Key to proceed.")
                st.stop()
    
    # Update global functions to use the dynamic key
    async def process_url_async_wrapper(url, skip_fact_check):
        return await process_url_async(url, skip_fact_check, api_key=api_key)
        
    async def process_batch_async_wrapper(urls, skip_fact_check):
        return await process_batch_async(urls, skip_fact_check, api_key=api_key)

    # Monkey patch or re-define the async functions in this scope for the buttons to use
    # Actually, simpler to just update the calls later, but let's redefine the wrappers
    # directly where they are needed or pass api_key to them.
    # To minimize changes to the rest of the file, we'll redefine the module-level functions
    # LOCALLY within main(), but Streamlit buttons call lambda or functions.
    # The existing code calls `process_url_async(url, skip_fact_check)`.
    # We should update `process_url_async` signature in the file first to accept api_key.


    # Handle batch restoration from Recents sidebar
    if st.session_state.restore_batch_id:
        batch_id = st.session_state.restore_batch_id
        st.session_state.restore_batch_id = None  # Clear to avoid re-triggering
        batch = get_cache().get_batch_by_id(batch_id)
        if batch and batch.results_json:
            try:
                results_data = json.loads(batch.results_json)
                results = [ProcessedResult.model_validate(r) for r in results_data]
                st.session_state.batch_results = results
                st.session_state.batch_urls = batch.urls
                st.success(f"📋 Restored batch from {batch.timestamp.strftime('%m/%d %H:%M')}")
            except Exception as e:
                logger.warning(f"Error restoring batch: {e}")
                st.error("Could not restore batch results.")

    # Tab selection using segmented control (allows programmatic switching)
    tab_options = ["Single URL", "Batch Processing"]
    desired_tab = "Batch Processing" if st.session_state.active_tab == "batch" else "Single URL"
    
    selected_tab = st.segmented_control("Mode", tab_options, default=desired_tab, key="tab_selector")
    
    # Update session state when user manually changes tab
    # Note: segmented_control can return None in some edge cases, so only update if we have a value
    if selected_tab is not None:
        if selected_tab == "Batch Processing":
            st.session_state.active_tab = "batch"
        else:
            st.session_state.active_tab = "single"

    # Use session state as source of truth for which content to display
    # This ensures correct rendering even when selected_tab is None
    if st.session_state.active_tab == "single":
        st.markdown("### Process a Single URL")

        # URL input
        url = st.text_input(
            "Enter URL",
            placeholder="https://example.com/article",
            value=st.session_state.get("selected_url", ""),
        )

        if st.button("🚀 Process URL", type="primary", disabled=not url):
            if url:
                with st.spinner("Processing... This may take 30-60 seconds."):
                    progress = st.progress(0, text="Initializing...")

                    try:
                        progress.progress(20, text="Extracting content...")
                        result = run_async(process_url_async_wrapper(url, skip_fact_check))

                        progress.progress(100, text="Complete!")

                        # Save to persistent cache
                        cache = get_cache()
                        cache.add_entry(CacheEntry(
                            url=url,
                            title=result.content.title if result.content else None,
                            status=result.status.value,
                            timestamp=datetime.now(),
                            source_type=result.source_type.value,
                        ))

                        st.markdown("---")
                        display_result(result)

                        # Export options
                        st.markdown("---")
                        st.markdown("#### Export Results")
                        export_cols = st.columns(2)
                        
                        with export_cols[0]:
                            result_json = result.model_dump_json(indent=2)
                            st.download_button(
                                "📥 Download JSON",
                                data=result_json,
                                file_name=f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json",
                            )
                        
                        with export_cols[1]:
                            # Generate PDF
                            try:
                                pdf_generator = PDFReportGenerator()
                                pdf_bytes = pdf_generator.generate(result)
                                pdf_filename = pdf_generator.get_filename(result)
                                st.download_button(
                                    "📄 Download PDF",
                                    data=pdf_bytes,
                                    file_name=pdf_filename,
                                    mime="application/pdf",
                                )
                            except Exception as pdf_error:
                                logger.exception("Error generating PDF")
                                st.warning("PDF generation unavailable")

                    except Exception as e:
                        logger.exception("Error processing URL: %s", url)
                        progress.empty()
                        st.error("Error processing URL. Please check the URL and try again.")

    elif st.session_state.active_tab == "batch":
        st.markdown("### Batch Process Multiple URLs")
        st.caption("Supports markdown-wrapped URLs, comments (#), and blank lines.")

        # Check for persisted batch results from session state
        if st.session_state.batch_results is not None:
            st.success("📋 Showing results from previous batch run. Click 'Clear Results' to start a new batch.")
            display_batch_results(st.session_state.batch_results)
            st.markdown("---")
            st.markdown("### Process New URLs")

        # Text area for multiple URLs
        urls_text = st.text_area(
            "Enter URLs (one per line)",
            placeholder="https://example.com/article1\n# Comments are skipped\nhttps://example.com/article2",
            height=150,
            key="batch_urls_input",
        )

        # Or upload a file
        uploaded_file = st.file_uploader("Or upload a text file with URLs", type=["txt"])

        if uploaded_file:
            urls_text = uploaded_file.getvalue().decode("utf-8")
            st.text_area("URLs from file:", value=urls_text, height=100, disabled=True)

        # Real-time URL parsing feedback
        if urls_text and urls_text.strip():
            from src.utils.url_validator import parse_url_input
            
            parse_result = parse_url_input(urls_text)
            
            # Show parsing summary
            cols = st.columns(4)
            with cols[0]:
                st.metric("Valid URLs", len(parse_result.valid_urls))
            with cols[1]:
                st.metric("Invalid", len(parse_result.invalid_lines), 
                         delta=None if not parse_result.invalid_lines else f"-{len(parse_result.invalid_lines)}")
            with cols[2]:
                st.metric("Duplicates", parse_result.duplicates_removed)
            with cols[3]:
                st.metric("Skipped", parse_result.skipped_lines)
            
            # Show warnings
            for warning in parse_result.warnings:
                st.warning(warning)
            
            # Show invalid lines
            if parse_result.invalid_lines:
                with st.expander(f"⚠️ {len(parse_result.invalid_lines)} Invalid Lines", expanded=False):
                    for line_num, content, reason in parse_result.invalid_lines:
                        st.text(f"Line {line_num}: {content[:60]}...")
                        st.caption(f"   Reason: {reason}")
            
            urls_to_process = parse_result.valid_urls
            can_process = len(urls_to_process) > 0
        else:
            urls_to_process = []
            can_process = False

        if st.button("🚀 Process All URLs", type="primary", disabled=not can_process):
            if urls_to_process:
                total_urls = len(urls_to_process)
                
                # Container for progress display
                progress_container = st.container()
                
                try:
                    with progress_container:
                        st.markdown(f"### ⏳ Processing {total_urls} URLs")
                        st.markdown("---")
                        
                        # Overall progress
                        progress_bar = st.progress(0)
                        
                        # Stats row
                        stats_cols = st.columns(4)
                        completed_metric = stats_cols[0].empty()
                        failed_metric = stats_cols[1].empty()
                        elapsed_metric = stats_cols[2].empty()
                        eta_metric = stats_cols[3].empty()
                        
                        # Current status
                        current_status = st.empty()
                        
                        # Per-URL status log
                        url_status_container = st.container()

                    # Initialize tracking variables
                    import time as time_module
                    start_time = time_module.time()
                    completed_count = 0
                    failed_count = 0
                    processing_times = []
                    results = []
                    
                    # Process URLs one at a time for better progress tracking
                    # Each URL gets a fresh agent to avoid event loop conflicts
                    for i, url in enumerate(urls_to_process):
                        # Update current status
                        current_status.info(f"🔄 Processing: {url[:70]}...")
                        
                        # Calculate ETA
                        elapsed = time_module.time() - start_time
                        if processing_times:
                            avg_time = sum(processing_times) / len(processing_times)
                            remaining = (total_urls - i) * avg_time
                            eta_str = f"{int(remaining // 60)}m {int(remaining % 60)}s"
                        else:
                            eta_str = "Calculating..."
                        
                        # Update metrics
                        completed_metric.metric("✅ Completed", completed_count)
                        failed_metric.metric("❌ Failed", failed_count)
                        elapsed_metric.metric("⏱️ Elapsed", f"{int(elapsed // 60)}m {int(elapsed % 60)}s")
                        eta_metric.metric("📊 ETA", eta_str)
                        
                        # Update progress bar
                        progress_bar.progress((i) / total_urls)
                        
                        # Process this URL with a fresh agent (via process_url_async)
                        url_start = time_module.time()
                        try:
                            result = run_async(process_url_async_wrapper(url, skip_fact_check))
                            results.append(result)
                            
                            url_time = time_module.time() - url_start
                            processing_times.append(url_time)
                            
                            if result.status == ProcessingStatus.COMPLETED:
                                completed_count += 1
                                with url_status_container:
                                    st.success(f"✅ {url[:60]}... ({int(url_time)}s)")
                            else:
                                failed_count += 1
                                with url_status_container:
                                    st.error(f"❌ {url[:60]}... - {result.error or 'Failed'}")
                        
                        except Exception as url_error:
                            failed_count += 1
                            url_time = time_module.time() - url_start
                            processing_times.append(url_time)
                            with url_status_container:
                                st.error(f"❌ {url[:60]}... - {str(url_error)[:50]}")
                            # Create a failed result
                            results.append(ProcessedResult(
                                url=url,
                                source_type=URLType.UNKNOWN,
                                status=ProcessingStatus.FAILED,
                                error=str(url_error),
                            ))
                
                    # Final update (only runs if processing completed without exception)
                    progress_bar.progress(1.0)
                    completed_metric.metric("✅ Completed", completed_count)
                    failed_metric.metric("❌ Failed", failed_count)
                    elapsed = time_module.time() - start_time
                    elapsed_metric.metric("⏱️ Total Time", f"{int(elapsed // 60)}m {int(elapsed % 60)}s")
                    eta_metric.metric("📊 Status", "Done!")
                    current_status.success(f"🎉 Completed processing {total_urls} URLs!")

                    # Save BATCH RUN to persistent cache (not individual entries)
                    from uuid import uuid4
                    cache = get_cache()
                    batch_run = BatchRun(
                        id=str(uuid4()),
                        urls=urls_to_process,
                        timestamp=datetime.now(),
                        url_count=len(results),
                        success_count=completed_count,
                        failed_count=failed_count,
                        results_json=json.dumps([r.model_dump(mode='json') for r in results]),
                    )
                    cache.add_batch_run(batch_run)

                    # Store in session state for persistence across reruns
                    st.session_state.batch_results = results
                    st.session_state.batch_urls = urls_to_process

                    # Display results using the reusable function
                    st.markdown("---")
                    display_batch_results(results, show_clear_button=True)

                except Exception as e:
                    logger.exception("Error processing batch URLs")
                    progress_bar.empty()
                    current_status.error("❌ Error processing URLs. Please check the logs and try again.")


if __name__ == "__main__":
    main()

