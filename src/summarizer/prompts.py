"""Prompts for LLM summarization."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.narrative.engine import NarrativeFramingEngine


# Base system prompt without narrative injection
BASE_SYSTEM_PROMPT = """You are an expert content analyst and summarizer. Your task is to analyze content and produce structured summaries that are:

1. **Accurate**: Only include information present in the source material
2. **Comprehensive**: Capture all key points and important details
3. **Objective**: Present information neutrally without editorial bias
4. **Well-structured**: Organize information logically

When analyzing content:
- Identify the main thesis or key message
- Extract 3-7 key points that support or explain the main message
- Identify important entities (people, organizations, locations, products)
- Assess the overall sentiment (positive, negative, neutral, or mixed)
- Note any implications or potential impacts discussed
- Pull notable quotes or citations as footnotes

**SLIDE CONTENT GENERATION (Critical):**

You MUST generate slide-ready content using "net-less copy" style:
- NO filler words (just, very, really, basically, actually)
- NO complete sentences - use punchy fragments
- Lead with NUMBERS and specific data points
- Use active voice only
- Front-load the most important information

**SLIDE TYPE DETECTION:**
Choose the slide type based on content:
- "bullets" or "bullets_image": Default for most content with key facts (use bullets_image if content has visual element)
- "quote": ONLY if there's a powerful statement from a NAMED executive/researcher/official
- "video": ONLY if content references or embeds a video (YouTube, Vimeo, demo)
- "chart": If content contains percentage data, growth numbers, or market comparisons
- "comparison": If content compares two products/companies/models side-by-side

**STRICT WORD LIMITS:**
- Headline: MAX 8 words (Example: "Nvidia Acquires Groq for $20B")
- Bullets: MAX 12 words each, 3-4 bullets only
- Quote: MAX 25 words
- Captions: MAX 12 words

**BULLET WRITING RULES:**
✓ GOOD: "$20B deal, largest in company history"
✓ GOOD: "90.4% accuracy on GPQA benchmark"
✓ GOOD: "API pricing: $0.50/1M input tokens"
✗ BAD: "The company announced that they have completed a deal"
✗ BAD: "According to the announcement, this represents"

Always suggest an image type that would complement the slide (e.g., "product screenshot", "CEO headshot", "data chart")."""

# Narrative injection placeholder - inserted between base prompt and JSON instruction
NARRATIVE_INJECTION_MARKER = "{{NARRATIVE_GUIDANCE}}"

# Final instruction that always comes at the end
JSON_INSTRUCTION = "\n\nAlways respond with valid JSON matching the requested schema."


def build_system_prompt(narrative_engine: Optional["NarrativeFramingEngine"] = None) -> str:
    """Build the complete system prompt with optional narrative injection.
    
    Args:
        narrative_engine: Optional narrative framing engine. If provided and
            enabled, its guidance will be injected into the prompt.
            
    Returns:
        Complete system prompt string.
    """
    parts = [BASE_SYSTEM_PROMPT]
    
    # Inject narrative guidance if engine is provided and enabled
    if narrative_engine is not None:
        injection = narrative_engine.get_system_prompt_injection()
        if injection:
            parts.append("\n\n**FRAMING GUIDANCE:**")
            parts.append(injection)
    
    parts.append(JSON_INSTRUCTION)
    
    return "".join(parts)


# Legacy constant for backward compatibility
SUMMARIZATION_SYSTEM_PROMPT = build_system_prompt()

SUMMARIZATION_USER_PROMPT = """Analyze the following content and provide a structured summary.

**Source URL**: {url}
**Source Type**: {source_type}
**Title**: {title}
**Author**: {author}
**Published**: {published_date}

---

**CONTENT**:

{content}

---

Provide a comprehensive structured summary including:
1. An executive summary (1-2 paragraphs)
2. Key points (3-7 bullet points)
3. Overall sentiment
4. Named entities (people, organizations, locations)
5. Implications or impacts discussed
6. Notable quotes or citations (as footnotes)
7. Main topics/themes covered

**SLIDE CONTENT (REQUIRED - USE NET-LESS COPY):**

Generate slide-ready content. THIS IS CRITICAL - follow these rules exactly:

1. **slide_type** - Choose ONE:
   - "bullets" or "bullets_image": For key facts (most common)
   - "quote": ONLY for powerful executive/researcher quotes
   - "video": ONLY if article contains video embed
   - "chart": For percentage/growth data
   - "comparison": For product/model comparisons

2. **headline**: MAX 8 WORDS. Example: "Nvidia Acquires Groq for $20B"

3. **bullets**: EXACTLY 3-4 bullets, MAX 12 words each
   ✓ "$20B deal, largest in company history"
   ✓ "90.4% accuracy on GPQA benchmark"
   ✓ "Hallucination rate drops to 5.8%"
   ✗ "The company announced that they completed a deal" (TOO WORDY)

4. **quote_text** + **quote_attribution**: Only if slide_type is "quote"

5. **video_url** + **video_caption**: Only if slide_type is "video"

6. **chart_caption**: Only if slide_type is "chart" (max 15 words)

7. **comparison_left** + **comparison_right**: Only if slide_type is "comparison"

8. **image_suggestion**: Always include (e.g., "product screenshot", "CEO headshot", "data chart")

Ensure your analysis is accurate and grounded in the source material."""

CLAIM_EXTRACTION_PROMPT = """Analyze the following content and extract specific, checkable factual claims.

Focus on claims that:
- Contain specific numbers, statistics, or percentages
- Reference scientific studies or research
- Quote official sources or spokespersons
- Make predictions or assertions about future events
- Reference historical events or past statements

**CONTENT**:

{content}

---

Extract up to {max_claims} specific, verifiable claims from this content. Each claim should be:
- Self-contained (understandable without additional context)
- Specific (not vague or opinion-based)
- Checkable (could be verified against external sources)

Return the claims as a JSON array of strings."""


