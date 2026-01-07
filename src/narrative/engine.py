"""Narrative Framing Engine.

Core engine that determines when and how to apply narrative framing
to content summaries.
"""

import logging
import re
from typing import Optional, TYPE_CHECKING

from src.narrative.themes import (
    NarrativeTheme,
    THEME_PROMPTS,
    THEME_KEYWORDS,
    THEME_DOMAINS,
    NEGATIVE_KEYWORDS,
    DOMAIN_KEYWORDS,
    SUBTLETY_PREFIXES,
    SUBTLETY_SUFFIXES,
    get_theme_from_string,
)

if TYPE_CHECKING:
    from src.config import Settings
    from src.models.schemas import ExtractedContent

logger = logging.getLogger(__name__)


class NarrativeFramingEngine:
    """Engine for applying narrative framing to content summaries.
    
    Analyzes content to determine if narrative framing is applicable,
    and generates prompt injections to guide LLM output framing.
    """
    
    def __init__(
        self,
        theme: NarrativeTheme = NarrativeTheme.ABUNDANCE,
        enabled: bool = True,
        subtlety: str = "moderate",
    ):
        """Initialize the narrative framing engine.
        
        Args:
            theme: The narrative theme to apply.
            enabled: Whether narrative framing is enabled.
            subtlety: Framing intensity - 'subtle', 'moderate', or 'prominent'.
        """
        self.theme = theme
        self.enabled = enabled
        
        if subtlety not in ["subtle", "moderate", "prominent"]:
            logger.warning(f"Invalid subtlety '{subtlety}', defaulting to 'moderate'")
            subtlety = "moderate"
        self.subtlety = subtlety
    
    @classmethod
    def from_settings(cls, settings: "Settings") -> "NarrativeFramingEngine":
        """Create engine from application Settings.
        
        Args:
            settings: Application settings with narrative configuration.
            
        Returns:
            Configured NarrativeFramingEngine instance.
        """
        theme = get_theme_from_string(settings.narrative_theme)
        
        return cls(
            theme=theme,
            enabled=settings.narrative_enabled,
            subtlety=settings.narrative_subtlety,
        )
    
    def should_apply(self, content: "ExtractedContent") -> bool:
        """Determine if narrative framing should be applied to content.
        
        Analyzes the content to check if:
        1. Engine is enabled
        2. Theme is not NONE
        3. Content domain is applicable
        4. Content has positive/neutral sentiment (not predominantly negative)
        5. Content has keywords that naturally align with theme
        
        Args:
            content: The extracted content to analyze.
            
        Returns:
            True if narrative framing should be applied.
        """
        # Quick checks first
        if not self.enabled:
            return False
        
        if self.theme == NarrativeTheme.NONE:
            return False
        
        # Get content text for analysis
        text = self._get_analysis_text(content)
        
        # Check for predominantly negative content
        if self._is_predominantly_negative(text):
            return False
        
        # Check domain applicability
        domain = self._detect_domain(content)
        applicable_domains = THEME_DOMAINS.get(self.theme, [])
        
        if domain not in applicable_domains and "general" not in applicable_domains:
            return False
        
        # Check for theme-aligned keywords
        if not self._has_applicable_themes(text):
            return False
        
        return True
    
    def get_system_prompt_injection(self) -> str:
        """Get the system prompt injection for the current theme.
        
        Returns:
            Prompt text to inject into system prompt, or empty string
            if framing is disabled or theme is NONE.
        """
        if not self.enabled or self.theme == NarrativeTheme.NONE:
            return ""
        
        base_prompt = THEME_PROMPTS.get(self.theme, "")
        
        if not base_prompt:
            return ""
        
        # Apply subtlety modifiers
        prefix = SUBTLETY_PREFIXES.get(self.subtlety, "")
        suffix = SUBTLETY_SUFFIXES.get(self.subtlety, "")
        
        return f"{prefix}{base_prompt.strip()}{suffix}"
    
    def get_user_prompt_injection(self) -> str:
        """Get optional user prompt injection.
        
        Currently returns empty string as framing is done via system prompt.
        Reserved for future use if per-article guidance is needed.
        
        Returns:
            Prompt text to inject into user prompt.
        """
        # User prompt injection is optional - currently not used
        # but method is provided for extensibility
        return ""
    
    def _get_analysis_text(self, content: "ExtractedContent") -> str:
        """Extract text for analysis from content.
        
        Args:
            content: The extracted content.
            
        Returns:
            Combined text for keyword analysis.
        """
        parts = []
        
        if content.metadata.title:
            parts.append(content.metadata.title)
        
        # Use first 2000 chars of raw text for analysis
        if content.raw_text:
            parts.append(content.raw_text[:2000])
        
        return " ".join(parts).lower()
    
    def _detect_domain(self, content: "ExtractedContent") -> str:
        """Detect the content domain based on keywords.
        
        Args:
            content: The extracted content.
            
        Returns:
            Detected domain string (e.g., 'technology', 'finance').
        """
        text = self._get_analysis_text(content)
        
        domain_scores: dict[str, int] = {}
        
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if domain == "general":
                continue
            
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return "general"
    
    def _is_predominantly_negative(self, text: str) -> bool:
        """Check if content is predominantly negative.
        
        Args:
            text: Lowercase text to analyze.
            
        Returns:
            True if content appears predominantly negative.
        """
        negative_count = sum(
            1 for kw in NEGATIVE_KEYWORDS 
            if re.search(rf'\b{re.escape(kw)}\w*', text, re.IGNORECASE)
        )
        
        # If more than 3 negative keywords, consider it negative
        return negative_count > 3
    
    def _has_applicable_themes(self, text: str) -> bool:
        """Check if content has keywords that align with theme.
        
        Args:
            text: Lowercase text to analyze.
            
        Returns:
            True if content has theme-aligned keywords.
        """
        theme_keywords = THEME_KEYWORDS.get(self.theme, [])
        
        if not theme_keywords:
            return False
        
        # Count matching keywords using prefix matching
        matches = sum(
            1 for kw in theme_keywords 
            if re.search(rf'\b{re.escape(kw)}\w*', text, re.IGNORECASE)
        )
        
        # Require at least 2 matching keywords
        return matches >= 2
