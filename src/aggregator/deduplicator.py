"""News deduplication and aggregation using Gemini AI.

This module identifies similar/duplicate news articles and merges them
into single aggregated entries with multiple sources.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

import google.generativeai as genai

from src.aggregator.prompts import (
    DEDUPLICATION_SYSTEM_PROMPT,
    DEDUPLICATION_USER_PROMPT,
    FINAL_REVIEW_SYSTEM_PROMPT,
    FINAL_REVIEW_USER_PROMPT,
)
from src.config import get_settings
from src.models.schemas import (
    AggregatedResult,
    AggregatedResultSet,
    ContentSummary,
    Entity,
    FactCheckReport,
    Footnote,
    ProcessedResult,
    ProcessingStatus,
    Sentiment,
    SourceReference,
    URLType,
)

logger = logging.getLogger(__name__)


class AggregationError(Exception):
    """Raised when aggregation fails."""
    pass


class NewsAggregator:
    """
    Aggregates similar news articles using Gemini AI.
    
    Identifies duplicate/similar articles covering the same story and merges
    them into single entries with multiple sources listed.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize the aggregator with Gemini."""
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model or settings.gemini_model

        if not self.api_key:
            raise AggregationError("Gemini API key is required")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=genai.GenerationConfig(
                temperature=0.2,  # Low temperature for consistent analysis
                top_p=0.8,
                max_output_tokens=8192,
            ),
        )

    def aggregate(
        self,
        results: List[ProcessedResult],
        perform_final_review: bool = True,
    ) -> AggregatedResultSet:
        """
        Aggregate similar articles from a list of processed results.

        Args:
            results: List of ProcessedResult objects to analyze and aggregate.
            perform_final_review: Whether to have Gemini review merged entries.

        Returns:
            AggregatedResultSet with merged and standalone entries.
        """
        # Filter to only completed results with summaries
        valid_results = [
            r for r in results
            if r.status == ProcessingStatus.COMPLETED and r.summary
        ]

        if not valid_results:
            logger.warning("No valid results to aggregate")
            return AggregatedResultSet(
                results=[],
                total_original=len(results),
                total_aggregated=0,
                duplicates_merged=0,
            )

        logger.info(f"Analyzing {len(valid_results)} articles for duplicates...")

        # Step 1: Identify duplicate groups using Gemini
        groups, standalone = self._identify_duplicates(valid_results)

        logger.info(f"Found {len(groups)} duplicate groups, {len(standalone)} standalone articles")

        # Step 2: Create aggregated results
        aggregated_results = []

        # Process grouped articles
        for group_info in groups:
            indices = group_info["indices"]
            unified_title = group_info["unified_title"]
            group_results = [valid_results[i] for i in indices]

            aggregated = self._merge_articles(group_results, unified_title)

            # Optional: Have Gemini review and refine the merged entry
            if perform_final_review and len(group_results) > 1:
                aggregated = self._final_review(aggregated)

            aggregated_results.append(aggregated)

        # Process standalone articles (convert to AggregatedResult format)
        for idx in standalone:
            result = valid_results[idx]
            aggregated = self._convert_to_aggregated(result)
            aggregated_results.append(aggregated)

        duplicates_merged = sum(len(g["indices"]) for g in groups if len(g["indices"]) > 1)

        return AggregatedResultSet(
            results=aggregated_results,
            total_original=len(results),
            total_aggregated=len(aggregated_results),
            duplicates_merged=duplicates_merged,
        )

    def _identify_duplicates(
        self,
        results: List[ProcessedResult],
    ) -> Tuple[List[Dict], List[int]]:
        """
        Use Gemini to identify groups of duplicate/similar articles.

        Returns:
            Tuple of (groups, standalone_indices)
        """
        # Prepare article summaries for analysis
        articles_text = self._format_articles_for_analysis(results)

        prompt = DEDUPLICATION_USER_PROMPT.format(
            count=len(results),
            articles=articles_text,
            max_index=len(results) - 1,
        )

        try:
            response = self.model.generate_content(
                [
                    {"role": "user", "parts": [DEDUPLICATION_SYSTEM_PROMPT]},
                    {"role": "model", "parts": ["I understand. I will analyze the articles and identify groups of similar stories that should be merged, returning a structured JSON response."]},
                    {"role": "user", "parts": [prompt]},
                ]
            )

            # Parse JSON response
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            result = json.loads(text)
            groups = result.get("groups", [])
            standalone = result.get("standalone", [])

            # Validate that all indices are accounted for
            all_indices = set()
            for group in groups:
                all_indices.update(group["indices"])
            all_indices.update(standalone)

            expected = set(range(len(results)))
            if all_indices != expected:
                logger.warning(f"Index mismatch in deduplication. Expected {expected}, got {all_indices}")
                # Fall back to treating all as standalone
                return [], list(range(len(results)))

            return groups, standalone

        except Exception as e:
            logger.error(f"Failed to identify duplicates: {e}")
            # Fall back to no grouping
            return [], list(range(len(results)))

    def _format_articles_for_analysis(self, results: List[ProcessedResult]) -> str:
        """Format articles for Gemini analysis."""
        parts = []
        for i, result in enumerate(results):
            title = result.content.title if result.content and result.content.title else "Untitled"
            source = result.content.site_name if result.content and result.content.site_name else "Unknown"
            summary = result.summary.executive_summary if result.summary else "No summary"
            topics = ", ".join(result.summary.topics) if result.summary and result.summary.topics else "N/A"

            parts.append(f"""
[Article {i}]
Title: {title}
Source: {source}
Topics: {topics}
Summary: {summary[:500]}...
""")
        return "\n".join(parts)

    def _merge_articles(
        self,
        results: List[ProcessedResult],
        unified_title: str,
    ) -> AggregatedResult:
        """
        Merge multiple articles into a single aggregated result.

        Concatenates key points, implications, entities, etc. from all sources.
        """
        # Create source references
        sources = []
        for result in results:
            source_ref = SourceReference(
                url=result.url,
                title=result.content.title if result.content else None,
                site_name=result.content.site_name if result.content else None,
                author=result.content.author if result.content else None,
                published_date=result.content.published_date if result.content else None,
                source_type=result.source_type,
            )
            sources.append(source_ref)

        # Concatenate all content
        all_key_points = []
        all_implications = []
        all_entities = []
        all_footnotes = []
        all_topics = set()
        all_summaries = []
        sentiments = []

        for result in results:
            if result.summary:
                all_key_points.extend(result.summary.key_points)
                all_implications.extend(result.summary.implications)
                all_entities.extend(result.summary.entities)
                all_footnotes.extend(result.summary.footnotes)
                all_topics.update(result.summary.topics)
                all_summaries.append(result.summary.executive_summary)
                sentiments.append(result.summary.sentiment)

        # Deduplicate key points (keep first occurrence, case-insensitive)
        seen_points = set()
        unique_key_points = []
        for point in all_key_points:
            point_lower = point.lower().strip()
            if point_lower not in seen_points:
                seen_points.add(point_lower)
                unique_key_points.append(point)
        all_key_points = unique_key_points

        # Deduplicate implications
        seen_implications = set()
        unique_implications = []
        for imp in all_implications:
            imp_lower = imp.lower().strip()
            if imp_lower not in seen_implications:
                seen_implications.add(imp_lower)
                unique_implications.append(imp)
        all_implications = unique_implications

        # Determine dominant sentiment
        if sentiments:
            sentiment_counts = {}
            for s in sentiments:
                sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
            dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)
        else:
            dominant_sentiment = Sentiment.NEUTRAL

        # Combine executive summaries
        combined_summary = " | ".join(all_summaries) if all_summaries else "No summary available."

        # Deduplicate entities by text
        seen_entities = set()
        unique_entities = []
        for entity in all_entities:
            if entity.text.lower() not in seen_entities:
                seen_entities.add(entity.text.lower())
                unique_entities.append(entity)

        # Re-number footnotes
        renumbered_footnotes = []
        for i, fn in enumerate(all_footnotes, 1):
            renumbered_footnotes.append(Footnote(
                id=i,
                source_text=fn.source_text,
                context=fn.context,
            ))

        # Create combined summary (respecting schema limits)
        # ContentSummary has max_length=10 for key_points
        combined_content_summary = ContentSummary(
            executive_summary=combined_summary,
            key_points=all_key_points[:10],  # Limit to 10 key points
            sentiment=dominant_sentiment,
            entities=unique_entities[:15],  # Limit entities
            implications=all_implications[:5],  # Limit implications
            footnotes=renumbered_footnotes[:5],  # Limit footnotes
            topics=list(all_topics)[:8],  # Limit topics
        )

        # Combine fact checks if present
        combined_fact_check = None
        fact_checks = [r.fact_check for r in results if r.fact_check]
        if fact_checks:
            combined_fact_check = self._merge_fact_checks(fact_checks)

        # Determine primary source type
        source_types = [r.source_type for r in results]
        primary_source_type = max(set(source_types), key=source_types.count)

        return AggregatedResult(
            title=unified_title,
            sources=sources,
            summary=combined_content_summary,
            source_type=primary_source_type,
            status=ProcessingStatus.COMPLETED,
            fact_check=combined_fact_check,
            is_aggregated=True,
            original_count=len(results),
        )

    def _merge_fact_checks(self, fact_checks: List[FactCheckReport]) -> FactCheckReport:
        """Merge multiple fact check reports."""
        total_claims = sum(fc.claims_analyzed for fc in fact_checks)
        all_verified = []
        all_unverified = []

        for fc in fact_checks:
            all_verified.extend(fc.verified_claims)
            all_unverified.extend(fc.unverified_claims)

        # Use the first publisher credibility found
        publisher_cred = None
        for fc in fact_checks:
            if fc.publisher_credibility:
                publisher_cred = fc.publisher_credibility
                break

        return FactCheckReport(
            claims_analyzed=total_claims,
            verified_claims=all_verified,
            unverified_claims=list(set(all_unverified)),  # Dedupe
            publisher_credibility=publisher_cred,
        )

    def _convert_to_aggregated(self, result: ProcessedResult) -> AggregatedResult:
        """Convert a single ProcessedResult to AggregatedResult format."""
        # Use empty string instead of "Untitled" for missing titles
        title = result.content.title if result.content and result.content.title else ""

        source_ref = SourceReference(
            url=result.url,
            title=title if title else None,  # Store None for source reference if no title
            site_name=result.content.site_name if result.content else None,
            author=result.content.author if result.content else None,
            published_date=result.content.published_date if result.content else None,
            source_type=result.source_type,
        )

        return AggregatedResult(
            title=title,
            sources=[source_ref],
            summary=result.summary,
            source_type=result.source_type,
            status=result.status,
            fact_check=result.fact_check,
            is_aggregated=False,
            original_count=1,
        )

    def _final_review(self, aggregated: AggregatedResult) -> AggregatedResult:
        """
        Have Gemini review and refine a merged entry.
        
        Removes redundancy and improves coherence.
        """
        try:
            key_points_text = "\n".join(f"- {p}" for p in aggregated.summary.key_points)
            implications_text = "\n".join(f"- {i}" for i in aggregated.summary.implications)
            topics_text = ", ".join(aggregated.summary.topics)

            prompt = FINAL_REVIEW_USER_PROMPT.format(
                source_count=len(aggregated.sources),
                title=aggregated.title,
                executive_summary=aggregated.summary.executive_summary,
                key_points=key_points_text,
                implications=implications_text,
                topics=topics_text,
            )

            response = self.model.generate_content(
                [
                    {"role": "user", "parts": [FINAL_REVIEW_SYSTEM_PROMPT]},
                    {"role": "model", "parts": ["I understand. I will review and refine the aggregated entry, removing redundancy while preserving unique information."]},
                    {"role": "user", "parts": [prompt]},
                ]
            )

            # Parse JSON response
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            refined = json.loads(text)

            # Update the aggregated result with refined content
            aggregated.title = refined.get("title", aggregated.title)
            aggregated.summary.executive_summary = refined.get(
                "executive_summary", aggregated.summary.executive_summary
            )
            aggregated.summary.key_points = refined.get(
                "key_points", aggregated.summary.key_points
            )
            aggregated.summary.implications = refined.get(
                "implications", aggregated.summary.implications
            )
            aggregated.summary.topics = refined.get(
                "topics", aggregated.summary.topics
            )

            logger.info(f"Refined aggregated entry: {aggregated.title}")

        except Exception as e:
            logger.warning(f"Failed to refine aggregated entry: {e}")
            # Keep original if refinement fails

        return aggregated

