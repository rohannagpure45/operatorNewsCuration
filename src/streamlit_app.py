"""Streamlit frontend for the News Curation Agent."""

import asyncio
import json
import logging
from datetime import datetime

import streamlit as st

# Configure logging for server-side error tracking
logger = logging.getLogger(__name__)

from src.agent import NewsAgent
from src.export.pdf_report import PDFReportGenerator
from src.models.schemas import ProcessedResult, ProcessingStatus, Sentiment, URLType


# Page configuration
st.set_page_config(
    page_title="News Curation Agent",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
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


async def process_url_async(url: str, skip_fact_check: bool = False):
    """Process a URL asynchronously."""
    agent = NewsAgent()
    try:
        result = await agent.process(url, skip_fact_check=skip_fact_check)
        return result
    finally:
        await agent.close()


async def process_batch_async(urls: list, skip_fact_check: bool = False):
    """Process multiple URLs asynchronously."""
    agent = NewsAgent()
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


def main():
    """Main Streamlit application."""
    # Sidebar
    with st.sidebar:
        st.title("📰 News Curation Agent")
        st.markdown("---")

        # Configuration
        st.markdown("### Settings")
        skip_fact_check = st.checkbox("Skip Fact-Checking", value=False, help="Skip the fact-checking step for faster processing")

        st.markdown("---")

        # History (stored in session state)
        if "history" not in st.session_state:
            st.session_state.history = []

        if st.session_state.history:
            st.markdown("### Recent URLs")
            for i, item in enumerate(reversed(st.session_state.history[-10:])):
                status_icon = "✅" if item["status"] == "completed" else "❌"
                if st.button(f"{status_icon} {item['url'][:40]}...", key=f"history_{i}"):
                    st.session_state.selected_url = item["url"]

        st.markdown("---")
        st.caption("Built with Trafilatura, Gemini, and Playwright")

    # Main content
    st.title("News Curation Agent")
    st.markdown("Extract, fact-check, and summarize content from news articles, Twitter/X, and SEC filings.")

    # Tabs for different input modes
    tab1, tab2 = st.tabs(["Single URL", "Batch Processing"])

    with tab1:
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
                        result = run_async(process_url_async(url, skip_fact_check))

                        progress.progress(100, text="Complete!")

                        # Add to history (keep only last 100 items)
                        st.session_state.history.append({
                            "url": url,
                            "status": result.status.value,
                            "timestamp": datetime.now().isoformat(),
                        })
                        st.session_state.history = st.session_state.history[-100:]

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

    with tab2:
        st.markdown("### Batch Process Multiple URLs")
        st.caption("Supports markdown-wrapped URLs, comments (#), and blank lines.")

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
                    agent = NewsAgent()
                    try:
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
                            
                            # Process this URL
                            url_start = time_module.time()
                            try:
                                result = run_async(agent.process(url, skip_fact_check=skip_fact_check))
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
                    finally:
                        # Always cleanup agent resources
                        run_async(agent.close())
                
                    # Final update (only runs if processing completed without exception)
                    progress_bar.progress(1.0)
                    completed_metric.metric("✅ Completed", completed_count)
                    failed_metric.metric("❌ Failed", failed_count)
                    elapsed = time_module.time() - start_time
                    elapsed_metric.metric("⏱️ Total Time", f"{int(elapsed // 60)}m {int(elapsed % 60)}s")
                    eta_metric.metric("📊 Status", "Done!")
                    current_status.success(f"🎉 Completed processing {total_urls} URLs!")

                    # Add to history
                    for result in results:
                        st.session_state.history.append({
                            "url": result.url,
                            "status": result.status.value,
                            "timestamp": datetime.now().isoformat(),
                        })
                    st.session_state.history = st.session_state.history[-100:]

                    # Display results
                    st.markdown("---")
                    st.markdown("### Results")
                    
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
                    
                    # Results display
                    for i, result in enumerate(results):
                        status_icon = "✅" if result.status == ProcessingStatus.COMPLETED else "❌"
                        with st.expander(f"{status_icon} Result {i+1}: {result.url[:60]}...", expanded=(i == 0)):
                            display_result(result)

                    # Export all results
                    st.markdown("---")
                    st.markdown("#### Export All Results")
                    export_cols = st.columns(2)
                    
                    with export_cols[0]:
                        all_results_json = json.dumps(
                            [r.model_dump() for r in results],
                            indent=2,
                            default=str,
                        )
                        st.download_button(
                            "📥 Download All (JSON)",
                            data=all_results_json,
                            file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json",
                        )
                    
                    with export_cols[1]:
                        # Generate batch PDF
                        try:
                            pdf_generator = PDFReportGenerator()
                            pdf_bytes = pdf_generator.generate_batch(results)
                            st.download_button(
                                "📄 Download All (PDF)",
                                data=pdf_bytes,
                                file_name=f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                mime="application/pdf",
                            )
                        except Exception as pdf_error:
                            logger.exception("Error generating batch PDF")
                            st.warning("PDF generation unavailable")

                except Exception as e:
                    logger.exception("Error processing batch URLs")
                    progress_bar.empty()
                    current_status.error("❌ Error processing URLs. Please check the logs and try again.")


if __name__ == "__main__":
    main()

