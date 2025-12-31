"""News aggregation and deduplication module.

This module provides functionality to identify and merge similar/duplicate
news articles using Gemini AI.
"""

from src.aggregator.deduplicator import NewsAggregator, AggregationError

__all__ = ["NewsAggregator", "AggregationError"]

