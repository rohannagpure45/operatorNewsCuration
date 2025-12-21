"""Tests for fact-checking functionality."""

import pytest

from src.enrichment.fact_check import FactChecker
from src.models.schemas import ClaimRating


class TestFactChecker:
    """Tests for the FactChecker class."""

    def test_rating_mapping(self):
        """Test rating text to enum mapping."""
        checker = FactChecker(api_key="test")

        # Test exact matches
        assert checker._map_rating("true") == ClaimRating.TRUE
        assert checker._map_rating("false") == ClaimRating.FALSE
        assert checker._map_rating("mostly true") == ClaimRating.MOSTLY_TRUE
        assert checker._map_rating("pants on fire") == ClaimRating.FALSE

        # Test partial matches
        assert checker._map_rating("Mostly True") == ClaimRating.MOSTLY_TRUE
        assert checker._map_rating("This is FALSE") == ClaimRating.FALSE

        # Test unknown ratings
        assert checker._map_rating("unknown rating") == ClaimRating.UNVERIFIED

    def test_claim_extraction(self):
        """Test heuristic claim extraction."""
        checker = FactChecker(api_key="test")

        content = """
        According to the latest report, sales increased by 50% last quarter.
        The company announced a new product launch.
        Studies show that exercise improves mental health.
        The weather is nice today.
        """

        claims = checker._extract_claims(content)

        # Should extract claims with indicators
        assert len(claims) >= 2
        assert any("50%" in c for c in claims)
        assert any("announced" in c.lower() for c in claims)

        # Should not extract simple statements
        assert not any("weather" in c.lower() for c in claims)


class TestFactCheckReport:
    """Tests for FactCheckReport model."""

    def test_empty_report(self):
        """Test creating an empty report."""
        from src.models.schemas import FactCheckReport

        report = FactCheckReport()
        assert report.claims_analyzed == 0
        assert len(report.verified_claims) == 0
        assert len(report.unverified_claims) == 0

    def test_report_with_claims(self):
        """Test creating a report with claims."""
        from src.models.schemas import FactCheckReport, FactCheckResult

        result = FactCheckResult(
            claim="Test claim",
            rating=ClaimRating.TRUE,
            source="TestSource",
        )

        report = FactCheckReport(
            claims_analyzed=1,
            verified_claims=[result],
            unverified_claims=[],
        )

        assert report.claims_analyzed == 1
        assert len(report.verified_claims) == 1
        assert report.verified_claims[0].rating == ClaimRating.TRUE

