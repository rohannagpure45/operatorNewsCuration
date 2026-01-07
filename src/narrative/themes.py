"""Narrative themes and prompt templates.

Defines available narrative themes and their associated prompt injections
for subtle content framing.
"""

from enum import Enum


class NarrativeTheme(Enum):
    """Available narrative themes for content framing."""
    
    ABUNDANCE = "abundance"
    HOPE = "hope"
    OPPORTUNITY = "opportunity"
    NONE = "none"


def get_theme_from_string(theme_str: str) -> NarrativeTheme:
    """Convert a string to NarrativeTheme enum.
    
    Args:
        theme_str: Theme name as string (case-insensitive).
        
    Returns:
        Corresponding NarrativeTheme, or NONE if invalid.
    """
    if not theme_str:
        return NarrativeTheme.NONE
    
    theme_lower = theme_str.lower().strip()
    
    for theme in NarrativeTheme:
        if theme.value == theme_lower:
            return theme
    
    return NarrativeTheme.NONE


# =============================================================================
# Theme Prompt Injections
# =============================================================================

# These prompts are subtly injected into the system prompt to guide the LLM
# toward emphasizing certain aspects without altering facts.

THEME_PROMPTS: dict[NarrativeTheme, str] = {
    NarrativeTheme.ABUNDANCE: """
When analyzing implications and impacts:
- Emphasize how developments could increase accessibility, reduce costs, or democratize resources
- Highlight efficiency gains, scalability improvements, and productivity enhancements
- Note potential for broader access to previously scarce resources or capabilities
- Frame technological progress in terms of unlocking new possibilities
- Where applicable, connect advancements to themes of shared prosperity and expanding opportunity
""",
    
    NarrativeTheme.HOPE: """
When analyzing implications and impacts:
- Emphasize forward-looking perspectives and potential positive trajectories
- Highlight resilience, adaptation, and problem-solving aspects
- Note how challenges are being addressed or could be overcome
- Frame developments in terms of progress and human ingenuity
- Where applicable, connect to themes of growth, learning, and improvement
""",
    
    NarrativeTheme.OPPORTUNITY: """
When analyzing implications and impacts:
- Emphasize emerging opportunities and new possibilities
- Highlight growth potential, market expansion, and innovation
- Note actionable insights and areas for engagement
- Frame developments in terms of doors opening and new horizons
- Where applicable, connect to themes of participation and value creation
""",
    
    NarrativeTheme.NONE: "",
}


# Subtlety level modifiers - adjust the intensity of framing
SUBTLETY_PREFIXES: dict[str, str] = {
    "subtle": "Without being overtly promotional, when naturally applicable, ",
    "moderate": "When the content supports it, ",
    "prominent": "",
}

SUBTLETY_SUFFIXES: dict[str, str] = {
    "subtle": "\nMaintain objectivity above all. Only apply these perspectives when they genuinely fit the content.",
    "moderate": "\nBalance these perspectives with objective analysis of challenges and limitations.",
    "prominent": "\nActively seek angles that support these themes while remaining factually accurate.",
}


# =============================================================================
# Content Detection Keywords
# =============================================================================

# Keywords used to detect if content is naturally suited for narrative framing

THEME_KEYWORDS: dict[NarrativeTheme, list[str]] = {
    NarrativeTheme.ABUNDANCE: [
        "growth", "expansion", "increase", "scale", "efficiency",
        "productivity", "democratize", "accessible", "affordable",
        "breakthrough", "innovation", "advancement", "improvement",
        "optimize", "streamline", "reduce cost", "lower price",
        "more access", "wider availability", "new capability",
    ],
    
    NarrativeTheme.HOPE: [
        "progress", "improve", "solution", "solve", "overcome",
        "recovery", "resilient", "adapt", "transform", "future",
        "promising", "potential", "opportunity", "advance", "achieve",
        "milestone", "success", "breakthrough", "development",
    ],
    
    NarrativeTheme.OPPORTUNITY: [
        "opportunity", "potential", "growth", "invest", "market",
        "expand", "new", "emerging", "startup", "venture",
        "innovation", "disrupt", "transform", "pioneer", "lead",
        "competitive", "advantage", "value", "return",
    ],
    
    NarrativeTheme.NONE: [],
}


# Negative sentiment keywords - content with these should not be framed
NEGATIVE_KEYWORDS: list[str] = [
    "layoff", "layoffs", "fired", "firing", "downturn", "recession",
    "bankruptcy", "collapse", "crisis", "disaster", "catastrophe",
    "scandal", "fraud", "death", "deaths", "killed", "dying",
    "war", "conflict", "attack", "violence", "crime",
    "plummet", "plunge", "crash", "tank", "devastat",
    "lawsuit", "sued", "investigation", "indictment",
]


# =============================================================================
# Domain Detection
# =============================================================================

# Domains where narrative framing is applicable

THEME_DOMAINS: dict[NarrativeTheme, list[str]] = {
    NarrativeTheme.ABUNDANCE: [
        "technology", "finance", "health", "energy", "education", "general",
    ],
    
    NarrativeTheme.HOPE: [
        "technology", "health", "science", "environment", "education", "general",
    ],
    
    NarrativeTheme.OPPORTUNITY: [
        "technology", "finance", "business", "startup", "general",
    ],
    
    NarrativeTheme.NONE: [],
}


# Keywords for detecting content domain
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "technology": [
        "ai", "artificial intelligence", "machine learning", "software",
        "hardware", "computer", "tech", "digital", "algorithm", "data",
        "cloud", "saas", "api", "developer", "code", "programming",
        "chip", "semiconductor", "processor", "gpu", "model",
    ],
    
    "finance": [
        "invest", "stock", "market", "fund", "capital", "equity",
        "revenue", "profit", "earnings", "valuation", "ipo", "acquisition",
        "merger", "funding", "venture", "portfolio", "asset",
    ],
    
    "health": [
        "health", "medical", "medicine", "drug", "pharmaceutical",
        "treatment", "therapy", "disease", "patient", "clinical",
        "hospital", "doctor", "fda", "biotech", "vaccine",
    ],
    
    "energy": [
        "energy", "solar", "wind", "renewable", "battery", "electric",
        "power", "grid", "utility", "oil", "gas", "nuclear", "clean",
        "carbon", "emission", "climate", "sustainable",
    ],
    
    "general": [],  # Fallback domain
}
