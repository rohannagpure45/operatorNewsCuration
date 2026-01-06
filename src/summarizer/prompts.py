"""Prompts for LLM summarization."""

SUMMARIZATION_SYSTEM_PROMPT = """You are an expert content analyst and summarizer. Your task is to analyze content and produce structured summaries that are:

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

**SLIDE CONTENT GENERATION:**
You must also generate slide-ready content optimized for presentations:

1. **Determine slide type** based on content:
   - "quote": If there's a powerful, quotable statement from a named person (executive, researcher, etc.)
   - "video": If the content references or embeds a video (YouTube, Vimeo, etc.)
   - "bullets": Default for most content - key facts and takeaways

2. **Generate short, punchy copy:**
   - Headline: Max 8 words, captures the core news
   - Bullets: Max 10 words each, 3-5 bullets with key facts/numbers
   - Quote (if applicable): Max 25 words, the most impactful quote
   - Video caption (if applicable): Max 12 words

3. **Copy style for slides:**
   - Lead with numbers and specific data points
   - Use active voice
   - Remove filler words
   - Front-load the most important information

Always respond with valid JSON matching the requested schema."""

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

**SLIDE CONTENT (Required):**
Generate slide-ready content with:
- slide_type: "bullets", "quote", or "video" (auto-detect based on content)
- headline: Short headline (max 8 words)
- bullets: 3-5 short bullet points (max 10 words each) with key facts/numbers
- quote_text + quote_attribution: If slide_type is "quote", include the best quote and who said it
- video_url + video_caption: If slide_type is "video", include URL and short caption

Examples of good slide bullets:
- "90.4% accuracy on GPQA benchmark"
- "$20B deal, largest in company history"
- "3x faster than previous model"
- "API pricing: $0.50/1M input tokens"

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

