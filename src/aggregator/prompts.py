"""Prompts for news deduplication and aggregation using Gemini."""

DEDUPLICATION_SYSTEM_PROMPT = """You are an expert news analyst tasked with identifying duplicate or highly similar news articles that cover the same story or event.

Your job is to analyze a list of news articles and group together those that are essentially covering the same news story, even if they have different titles, sources, or slightly different angles.

Articles should be grouped together if they:
- Cover the exact same news event or announcement
- Report on the same company action, product launch, or development
- Discuss the same research finding, policy change, or industry trend
- Are essentially the same story from different news outlets

Articles should NOT be grouped if they:
- Cover different aspects of a broader topic (e.g., two separate AI developments from different companies)
- Are from the same source but cover different stories
- Discuss the same company but regarding different news events
- Are only tangentially related through shared themes

Be conservative: only group articles when you're confident they cover the same specific story."""

DEDUPLICATION_USER_PROMPT = """Analyze the following {count} news articles and identify groups of articles that cover the same story.

For each group of similar articles:
1. Provide the indices of articles that belong together (0-indexed)
2. Suggest a unified title that captures the essence of the story
3. Briefly explain why these articles were grouped

Articles to analyze:
{articles}

Return your analysis as a JSON object with the following structure:
{{
    "groups": [
        {{
            "indices": [0, 3, 7],
            "unified_title": "Unified title for this story group",
            "reason": "Brief explanation of why these articles cover the same story"
        }}
    ],
    "standalone": [1, 2, 4, 5, 6]
}}

Where:
- "groups" contains arrays of article indices that should be merged together
- "standalone" contains indices of articles that don't have duplicates and should remain separate

Important: Every article index (0 to {max_index}) must appear exactly once, either in a group or in standalone."""


FINAL_REVIEW_SYSTEM_PROMPT = """You are an expert editor reviewing a curated news briefing. Your task is to review the aggregated news entries and ensure they are coherent, non-redundant, and professionally presented.

For each aggregated entry (combining multiple source articles), ensure:
1. The unified title accurately captures the main story
2. Key points are not redundant (remove duplicates while preserving unique information)
3. The executive summary is coherent and comprehensive
4. Implications are distinct and valuable

You may:
- Refine titles for clarity
- Remove duplicate key points while keeping unique insights
- Consolidate overlapping implications
- Improve the flow and readability of combined content"""

FINAL_REVIEW_USER_PROMPT = """Review and refine the following aggregated news entry that combines {source_count} articles:

Title: {title}

Executive Summary (combined from sources):
{executive_summary}

Key Points (from all sources):
{key_points}

Implications (from all sources):
{implications}

Topics: {topics}

Please return a refined version as JSON with:
{{
    "title": "Refined unified title",
    "executive_summary": "Coherent, non-redundant executive summary",
    "key_points": ["Distinct key point 1", "Distinct key point 2", ...],
    "implications": ["Distinct implication 1", ...],
    "topics": ["topic1", "topic2", ...]
}}

Focus on removing redundancy while preserving all unique, valuable information from the source articles."""

