"""Content enrichment: fact-checking and fallback mechanisms."""

from .fact_check import FactChecker, FactCheckResult
from .wayback import WaybackFetcher

__all__ = ["FactChecker", "FactCheckResult", "WaybackFetcher"]
