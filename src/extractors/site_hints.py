"""Site-specific hints and workarounds for known problematic websites."""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class SiteHint:
    """Information about a known problematic site with fallback strategies."""
    
    name: str
    pattern: str
    issue: str
    hint: str
    # RSS/Atom feed URL for content extraction
    rss_feed: Optional[str] = None
    # Legacy alias for rss_feed
    alternative: Optional[str] = None
    # Whether to try archive.today
    try_archive_today: bool = False
    # Whether to try Google Cache
    try_google_cache: bool = False
    # Whether site requires authentication
    requires_auth: bool = False
    # Whether site has a paywall
    has_paywall: bool = False
    # Domain for NewsAPI search (if different from URL domain)
    newsapi_domain: Optional[str] = None
    # Whether to prefer browser extraction (for Cloudflare-protected sites)
    prefer_browser: bool = False


# Known problematic sites with their specific issues and fallback strategies
KNOWN_SITES = [
    SiteHint(
        name="OpenAI",
        pattern=r"^https?://(www\.)?openai\.com/",
        issue="Cloudflare Turnstile JS challenge",
        hint="OpenAI uses aggressive bot protection. Try their RSS feed or official API.",
        rss_feed="https://openai.com/news/rss",
        alternative="https://openai.com/news/rss",
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=False,
        has_paywall=False,
        prefer_browser=True,  # Cloudflare sites work better with browser
    ),
    SiteHint(
        name="Bloomberg",
        pattern=r"^https?://(www\.)?bloomberg\.com/",
        issue="Paywall + advanced bot detection",
        hint="Bloomberg requires a subscription. Trying archive services.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=True,
        has_paywall=True,
        newsapi_domain="bloomberg.com",
    ),
    SiteHint(
        name="WSJ",
        pattern=r"^https?://(www\.)?wsj\.com/",
        issue="Paywall with metered access",
        hint="WSJ has a soft paywall. Trying archive services.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=True,
        has_paywall=True,
        newsapi_domain="wsj.com",
    ),
    SiteHint(
        name="FT",
        pattern=r"^https?://(www\.)?ft\.com/",
        issue="Paywall + registration wall",
        hint="Financial Times requires subscription. Trying archive services.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=True,
        has_paywall=True,
        newsapi_domain="ft.com",
    ),
    SiteHint(
        name="NYT",
        pattern=r"^https?://(www\.)?nytimes\.com/",
        issue="Paywall with limited free articles",
        hint="New York Times has metered paywall. Trying archive services.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=False,
        has_paywall=True,
        newsapi_domain="nytimes.com",
    ),
    SiteHint(
        name="Anthropic",
        pattern=r"^https?://(www\.)?anthropic\.com/",
        issue="Cloudflare protection",
        hint="Anthropic uses Cloudflare protection. Try their RSS feed.",
        rss_feed="https://www.anthropic.com/rss.xml",
        alternative="https://www.anthropic.com/rss.xml",
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=False,
        has_paywall=False,
        prefer_browser=True,  # Cloudflare sites work better with browser
    ),
    SiteHint(
        name="Google Blog",
        pattern=r"^https?://blog\.google/",
        issue="May use bot protection",
        hint="Google Blog sometimes blocks automated access.",
        rss_feed="https://blog.google/rss/",
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=False,
        has_paywall=False,
    ),
    SiteHint(
        name="LinkedIn",
        pattern=r"^https?://(www\.)?linkedin\.com/",
        issue="Login wall + bot detection",
        hint="LinkedIn requires authentication for most content.",
        rss_feed=None,
        try_archive_today=False,
        try_google_cache=False,
        requires_auth=True,
        has_paywall=False,
    ),
    SiteHint(
        name="Medium (paywalled)",
        pattern=r"^https?://(www\.)?medium\.com/(?!.*\?source=friends_link)",
        issue="Member-only content",
        hint="This Medium article may be behind their paywall. Try finding a friend link.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=True,
        has_paywall=True,
    ),
    SiteHint(
        name="The Economist",
        pattern=r"^https?://(www\.)?economist\.com/",
        issue="Paywall with limited free articles",
        hint="The Economist has a metered paywall. Trying archive services.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=False,
        has_paywall=True,
        newsapi_domain="economist.com",
    ),
    SiteHint(
        name="The Information",
        pattern=r"^https?://(www\.)?theinformation\.com/",
        issue="Hard paywall",
        hint="The Information has a strict paywall. Archive services may help.",
        rss_feed=None,
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=True,
        has_paywall=True,
    ),
    SiteHint(
        name="Reuters",
        pattern=r"^https?://(www\.)?reuters\.com/",
        issue="Bot protection",
        hint="Reuters may block automated access.",
        rss_feed="https://www.reuters.com/rssfeed/topNews",
        try_archive_today=True,
        try_google_cache=True,
        requires_auth=False,
        has_paywall=False,
        newsapi_domain="reuters.com",
    ),
]


def get_site_hint(url: str) -> Optional[SiteHint]:
    """
    Get site-specific hint for a URL.
    
    Args:
        url: The URL to check.
        
    Returns:
        SiteHint if the URL matches a known problematic site, None otherwise.
    """
    for site in KNOWN_SITES:
        if re.match(site.pattern, url, re.IGNORECASE):
            return site
    return None


def get_error_message(url: str, error: str) -> str:
    """
    Get an enhanced error message with site-specific hints.
    
    Args:
        url: The URL that failed.
        error: The original error message.
        
    Returns:
        Enhanced error message with helpful hints.
    """
    hint = get_site_hint(url)
    
    if hint:
        msg = f"{error}\n"
        msg += f"\n[Site: {hint.name}]\n"
        msg += f"Known issue: {hint.issue}\n"
        msg += f"Suggestion: {hint.hint}"
        
        if hint.alternative:
            msg += f"\nAlternative source: {hint.alternative}"
        
        if hint.has_paywall:
            msg += "\nNote: This site has a paywall."
        
        return msg
    
    # Generic hints based on error type
    if "403" in error:
        return f"{error}\n\nThis site blocked our request. It may have bot protection or require authentication."
    elif "timeout" in error.lower():
        return f"{error}\n\nThe site took too long to respond. It may be using a JavaScript challenge."
    elif "429" in error:
        return f"{error}\n\nRate limited by the site. Wait a moment before retrying."
    
    return error


def is_likely_paywalled(url: str) -> bool:
    """Check if a URL is likely behind a paywall."""
    hint = get_site_hint(url)
    return hint.has_paywall if hint else False


def get_alternative_source(url: str) -> Optional[str]:
    """Get alternative source URL if available (legacy, prefer get_rss_feed)."""
    hint = get_site_hint(url)
    return hint.alternative if hint else None


def get_rss_feed(url: str) -> Optional[str]:
    """
    Get RSS feed URL for a site if available.
    
    Args:
        url: The article URL.
        
    Returns:
        RSS feed URL if the site has one configured, None otherwise.
    """
    hint = get_site_hint(url)
    if hint:
        return hint.rss_feed or hint.alternative
    return None


def should_try_archive_today(url: str) -> bool:
    """Check if we should try archive.today for this URL."""
    hint = get_site_hint(url)
    return hint.try_archive_today if hint else False


def should_try_google_cache(url: str) -> bool:
    """Check if we should try Google Cache for this URL."""
    hint = get_site_hint(url)
    return hint.try_google_cache if hint else False


def get_newsapi_domain(url: str) -> Optional[str]:
    """Get the domain to use for NewsAPI searches."""
    hint = get_site_hint(url)
    if hint and hint.newsapi_domain:
        return hint.newsapi_domain
    # Fall back to extracting domain from URL
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return None


def should_prefer_browser(url: str) -> bool:
    """
    Check if browser extraction should be prioritized for this URL.
    
    This is typically true for Cloudflare-protected sites where:
    1. Primary httpx extraction fails with 403
    2. RSS feeds are also blocked by Cloudflare
    3. Archive services may not have the page
    4. But a real browser can successfully load the page
    
    Args:
        url: The URL to check.
        
    Returns:
        True if browser should be tried before other fallbacks.
    """
    hint = get_site_hint(url)
    return hint.prefer_browser if hint else False

