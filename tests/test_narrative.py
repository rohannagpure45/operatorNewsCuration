"""Tests for Narrative Theme System.

Comprehensive test coverage for the narrative framing engine that autonomously
detects when articles can be framed with abundance/hope themes and subtly
injects narrative framing into LLM outputs.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# =============================================================================
# Test NarrativeTheme Enum and Theme Data
# =============================================================================


class TestNarrativeTheme:
    """Tests for NarrativeTheme enum and theme configuration data."""

    def test_theme_values(self):
        """Test that all expected theme values exist."""
        from src.narrative.themes import NarrativeTheme
        
        assert NarrativeTheme.ABUNDANCE.value == "abundance"
        assert NarrativeTheme.HOPE.value == "hope"
        assert NarrativeTheme.OPPORTUNITY.value == "opportunity"
        assert NarrativeTheme.NONE.value == "none"

    def test_theme_prompts_mapping(self):
        """Test that each theme has a corresponding prompt template."""
        from src.narrative.themes import NarrativeTheme, THEME_PROMPTS
        
        # Every theme except NONE should have a prompt
        for theme in NarrativeTheme:
            if theme != NarrativeTheme.NONE:
                assert theme in THEME_PROMPTS, f"Missing prompt for {theme}"
                assert len(THEME_PROMPTS[theme]) > 0, f"Empty prompt for {theme}"
        
        # NONE should either be missing or empty
        if NarrativeTheme.NONE in THEME_PROMPTS:
            assert THEME_PROMPTS[NarrativeTheme.NONE] == ""

    def test_theme_keywords_mapping(self):
        """Test that each theme has associated detection keywords."""
        from src.narrative.themes import NarrativeTheme, THEME_KEYWORDS
        
        # Every theme except NONE should have keywords
        for theme in NarrativeTheme:
            if theme != NarrativeTheme.NONE:
                assert theme in THEME_KEYWORDS, f"Missing keywords for {theme}"
                assert isinstance(THEME_KEYWORDS[theme], list)
                assert len(THEME_KEYWORDS[theme]) > 0, f"No keywords for {theme}"

    def test_theme_domains_mapping(self):
        """Test that themes are mapped to applicable content domains."""
        from src.narrative.themes import NarrativeTheme, THEME_DOMAINS
        
        expected_domains = ["technology", "finance", "health", "energy", "general"]
        
        for theme in NarrativeTheme:
            if theme != NarrativeTheme.NONE:
                assert theme in THEME_DOMAINS, f"Missing domains for {theme}"
                assert isinstance(THEME_DOMAINS[theme], list)
                # Should cover at least some domains
                assert len(THEME_DOMAINS[theme]) > 0

    def test_get_theme_from_string(self):
        """Test converting string to NarrativeTheme enum."""
        from src.narrative.themes import NarrativeTheme, get_theme_from_string
        
        assert get_theme_from_string("abundance") == NarrativeTheme.ABUNDANCE
        assert get_theme_from_string("ABUNDANCE") == NarrativeTheme.ABUNDANCE
        assert get_theme_from_string("hope") == NarrativeTheme.HOPE
        assert get_theme_from_string("opportunity") == NarrativeTheme.OPPORTUNITY
        assert get_theme_from_string("none") == NarrativeTheme.NONE
        assert get_theme_from_string("invalid") == NarrativeTheme.NONE
        assert get_theme_from_string("") == NarrativeTheme.NONE


# =============================================================================
# Test NarrativeFramingEngine
# =============================================================================


class TestNarrativeFramingEngine:
    """Tests for the NarrativeFramingEngine class."""

    @pytest.fixture
    def mock_tech_content(self):
        """Create mock extracted content for tech articles."""
        from src.models.schemas import ExtractedContent, ContentMetadata, URLType
        
        return ExtractedContent(
            url="https://example.com/ai-breakthrough",
            url_type=URLType.NEWS_ARTICLE,
            raw_text="""
            OpenAI announces breakthrough in AI efficiency. The new model 
            achieves 90% cost reduction while improving performance. This 
            advancement could democratize access to AI technology for 
            businesses of all sizes. Researchers predict widespread adoption 
            will lead to significant productivity gains across industries.
            """,
            metadata=ContentMetadata(
                title="AI Breakthrough Promises Efficiency Gains",
                author="Tech Reporter",
                published_date=datetime.now(timezone.utc),
            ),
        )

    @pytest.fixture
    def mock_negative_content(self):
        """Create mock extracted content with negative sentiment."""
        from src.models.schemas import ExtractedContent, ContentMetadata, URLType
        
        return ExtractedContent(
            url="https://example.com/layoffs",
            url_type=URLType.NEWS_ARTICLE,
            raw_text="""
            Major tech company announces massive layoffs. 10,000 employees 
            will lose their jobs by end of quarter. Stock prices plummeted 
            15% on the news. Analysts warn of prolonged downturn. Economic 
            uncertainty looms as recession fears mount.
            """,
            metadata=ContentMetadata(
                title="Tech Giant Announces Major Layoffs",
                author="Business Reporter",
                published_date=datetime.now(timezone.utc),
            ),
        )

    @pytest.fixture
    def mock_finance_content(self):
        """Create mock extracted content for finance articles."""
        from src.models.schemas import ExtractedContent, ContentMetadata, URLType
        
        return ExtractedContent(
            url="https://example.com/investment-growth",
            url_type=URLType.NEWS_ARTICLE,
            raw_text="""
            Clean energy investments surge to record levels with growth potential.
            Solar and wind capacity additions exceeded expectations by 40%. 
            The expansion of renewable infrastructure democratizes access to 
            affordable power. Efficiency gains and productivity improvements 
            continue as costs decline. The transition to renewable energy 
            is accelerating, creating new opportunities for investors.
            """,
            metadata=ContentMetadata(
                title="Clean Energy Investments Hit Record High",
                author="Finance Reporter",
                published_date=datetime.now(timezone.utc),
            ),
        )

    def test_init_with_theme(self):
        """Test engine initialization with a theme."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        
        assert engine.theme == NarrativeTheme.ABUNDANCE
        assert engine.enabled is True

    def test_init_disabled(self):
        """Test engine initialization in disabled state."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(
            theme=NarrativeTheme.ABUNDANCE, 
            enabled=False
        )
        
        assert engine.enabled is False

    def test_init_with_subtlety(self):
        """Test engine initialization with subtlety levels."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        for subtlety in ["subtle", "moderate", "prominent"]:
            engine = NarrativeFramingEngine(
                theme=NarrativeTheme.ABUNDANCE,
                subtlety=subtlety,
            )
            assert engine.subtlety == subtlety

    def test_should_apply_tech_content(self, mock_tech_content):
        """Test that engine applies to tech content with positive angles."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        
        assert engine.should_apply(mock_tech_content) is True

    def test_should_apply_finance_content(self, mock_finance_content):
        """Test that engine applies to finance content with growth themes."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        
        assert engine.should_apply(mock_finance_content) is True

    def test_should_not_apply_negative_content(self, mock_negative_content):
        """Test that engine does NOT apply to predominantly negative content."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        
        # Should not apply to layoffs/recession content
        assert engine.should_apply(mock_negative_content) is False

    def test_should_not_apply_when_disabled(self, mock_tech_content):
        """Test that disabled engine never applies."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(
            theme=NarrativeTheme.ABUNDANCE,
            enabled=False,
        )
        
        assert engine.should_apply(mock_tech_content) is False

    def test_should_not_apply_none_theme(self, mock_tech_content):
        """Test that NONE theme never applies framing."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.NONE)
        
        assert engine.should_apply(mock_tech_content) is False

    def test_get_system_prompt_injection(self):
        """Test system prompt injection generation."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        injection = engine.get_system_prompt_injection()
        
        assert isinstance(injection, str)
        assert len(injection) > 0
        # Should contain guidance about framing
        assert any(word in injection.lower() for word in 
                   ["opportunity", "potential", "positive", "benefit", "growth"])

    def test_get_system_prompt_injection_when_disabled(self):
        """Test that disabled engine returns empty injection."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(
            theme=NarrativeTheme.ABUNDANCE,
            enabled=False,
        )
        injection = engine.get_system_prompt_injection()
        
        assert injection == ""

    def test_get_user_prompt_injection(self):
        """Test user prompt injection generation."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.HOPE)
        injection = engine.get_user_prompt_injection()
        
        assert isinstance(injection, str)
        # User prompt injection may be optional/empty for some themes

    def test_detect_domain_technology(self, mock_tech_content):
        """Test domain detection for technology content."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        domain = engine._detect_domain(mock_tech_content)
        
        assert domain == "technology"

    def test_detect_domain_finance(self, mock_finance_content):
        """Test domain detection for finance content."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        domain = engine._detect_domain(mock_finance_content)
        
        # Could be finance or energy depending on keyword weights
        assert domain in ["finance", "energy"]

    def test_subtlety_affects_injection(self):
        """Test that subtlety level affects prompt injection."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        subtle_engine = NarrativeFramingEngine(
            theme=NarrativeTheme.ABUNDANCE,
            subtlety="subtle",
        )
        prominent_engine = NarrativeFramingEngine(
            theme=NarrativeTheme.ABUNDANCE,
            subtlety="prominent",
        )
        
        subtle_injection = subtle_engine.get_system_prompt_injection()
        prominent_injection = prominent_engine.get_system_prompt_injection()
        
        # Injections should differ based on subtlety level
        assert subtle_injection != prominent_injection
        # Subtle should contain objectivity guidance
        assert "objectivity" in subtle_injection.lower()
        # Prominent should be more direct
        assert "actively seek" in prominent_injection.lower()


# =============================================================================
# Test Configuration
# =============================================================================


class TestNarrativeConfig:
    """Tests for narrative configuration in Settings."""

    def test_config_default_values(self):
        """Test default configuration values."""
        # Test with minimal env vars
        with patch.dict("os.environ", {
            "GEMINI_API_KEY": "test-key",
        }, clear=True):
            from src.config import Settings
            
            settings = Settings(gemini_api_key="test-key")
            
            assert settings.narrative_theme == "abundance"
            assert settings.narrative_enabled is True
            assert settings.narrative_subtlety == "moderate"

    def test_config_theme_parsing(self):
        """Test theme configuration parsing."""
        with patch.dict("os.environ", {
            "GEMINI_API_KEY": "test-key",
            "NARRATIVE_THEME": "hope",
            "NARRATIVE_ENABLED": "true",
        }, clear=True):
            from src.config import Settings
            
            settings = Settings(
                gemini_api_key="test-key",
                narrative_theme="hope",
            )
            
            assert settings.narrative_theme == "hope"

    def test_config_disabled(self):
        """Test disabling narrative feature via config."""
        from src.config import Settings
        
        settings = Settings(
            gemini_api_key="test-key",
            narrative_enabled=False,
        )
        
        assert settings.narrative_enabled is False

    def test_config_subtlety_levels(self):
        """Test subtlety level configuration."""
        from src.config import Settings
        
        for level in ["subtle", "moderate", "prominent"]:
            settings = Settings(
                gemini_api_key="test-key",
                narrative_subtlety=level,
            )
            assert settings.narrative_subtlety == level


# =============================================================================
# Test Integration
# =============================================================================


class TestNarrativeIntegration:
    """Integration tests for narrative + summarizer."""

    @pytest.fixture
    def mock_content(self):
        """Create mock extracted content."""
        from src.models.schemas import ExtractedContent, ContentMetadata, URLType
        
        return ExtractedContent(
            url="https://example.com/article",
            url_type=URLType.NEWS_ARTICLE,
            raw_text="Test content about technology advancement and growth.",
            metadata=ContentMetadata(
                title="Test Article",
                author="Test Author",
                published_date=datetime.now(timezone.utc),
            ),
        )

    def test_create_engine_from_config(self):
        """Test creating engine from Settings configuration."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        from src.config import Settings
        
        settings = Settings(
            gemini_api_key="test-key",
            narrative_theme="abundance",
            narrative_enabled=True,
            narrative_subtlety="moderate",
        )
        
        engine = NarrativeFramingEngine.from_settings(settings)
        
        assert engine.theme == NarrativeTheme.ABUNDANCE
        assert engine.enabled is True
        assert engine.subtlety == "moderate"

    def test_build_prompt_with_injection(self, mock_content):
        """Test that prompts are properly built with narrative injection."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        from src.summarizer.prompts import (
            SUMMARIZATION_SYSTEM_PROMPT,
            build_system_prompt,
        )
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        
        # If engine decides to apply
        if engine.should_apply(mock_content):
            injection = engine.get_system_prompt_injection()
            full_prompt = build_system_prompt(engine)
            
            assert injection in full_prompt

    def test_prompt_without_injection_when_disabled(self, mock_content):
        """Test prompts without injection when engine is disabled."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        from src.summarizer.prompts import (
            SUMMARIZATION_SYSTEM_PROMPT,
            build_system_prompt,
        )
        
        engine = NarrativeFramingEngine(
            theme=NarrativeTheme.ABUNDANCE,
            enabled=False,
        )
        
        full_prompt = build_system_prompt(engine)
        
        # Should be base prompt without additions
        assert "opportunity" not in full_prompt.lower() or \
               SUMMARIZATION_SYSTEM_PROMPT in full_prompt


# =============================================================================
# Test No Circular Dependencies
# =============================================================================


class TestNoDependencyCycles:
    """Tests to verify no circular import dependencies."""

    def test_import_narrative_module(self):
        """Test that narrative module can be imported cleanly."""
        # This should not raise ImportError
        from src.narrative import NarrativeFramingEngine, NarrativeTheme
        
        assert NarrativeFramingEngine is not None
        assert NarrativeTheme is not None

    def test_import_order_narrative_then_summarizer(self):
        """Test importing narrative before summarizer."""
        from src.narrative import NarrativeFramingEngine
        from src.summarizer.llm import Summarizer
        
        assert NarrativeFramingEngine is not None
        assert Summarizer is not None

    def test_import_order_summarizer_then_narrative(self):
        """Test importing summarizer before narrative."""
        from src.summarizer.llm import Summarizer
        from src.narrative import NarrativeFramingEngine
        
        assert Summarizer is not None
        assert NarrativeFramingEngine is not None

    def test_import_config_then_narrative(self):
        """Test importing config before narrative."""
        from src.config import get_settings
        from src.narrative import NarrativeFramingEngine
        
        assert get_settings is not None
        assert NarrativeFramingEngine is not None


# =============================================================================
# Test Bug Fixes - Added for keyword prefix matching and subtlety validation
# =============================================================================


class TestKeywordPrefixMatching:
    """Tests for keyword prefix matching (word variants like grows/growth)."""

    @pytest.fixture
    def content_with_word_variants(self):
        """Content using word variants that should match keywords."""
        from src.models.schemas import ExtractedContent, ContentMetadata, URLType
        
        return ExtractedContent(
            url="https://example.com/tech-article",
            url_type=URLType.NEWS_ARTICLE,
            raw_text="""
            The company's revenue grows rapidly as efficiency improves.
            New innovations are expanding access to AI technology.
            The scaling of operations produces significant productivity gains.
            """,
            metadata=ContentMetadata(
                title="Company Expanding Operations",
                author="Tech Reporter",
                published_date=datetime.now(timezone.utc),
            ),
        )

    def test_word_variants_match_keywords(self, content_with_word_variants):
        """Test that 'grows' matches 'growth', 'expanding' matches 'expansion'."""
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        engine = NarrativeFramingEngine(theme=NarrativeTheme.ABUNDANCE)
        
        # Should apply because word variants match the keywords
        # "grows" should match "growth", "expanding" should match "expansion"
        assert engine.should_apply(content_with_word_variants) is True


class TestSubtletyValidation:
    """Tests for invalid subtlety value handling."""

    def test_invalid_subtlety_logs_warning(self, caplog):
        """Test that invalid subtlety value logs a warning."""
        import logging
        from src.narrative.themes import NarrativeTheme
        from src.narrative.engine import NarrativeFramingEngine
        
        with caplog.at_level(logging.WARNING):
            engine = NarrativeFramingEngine(
                theme=NarrativeTheme.ABUNDANCE,
                subtlety="invalid_value",
            )
        
        # Should default to moderate
        assert engine.subtlety == "moderate"
        
        # Should have logged a warning
        assert any("invalid" in record.message.lower() for record in caplog.records)

