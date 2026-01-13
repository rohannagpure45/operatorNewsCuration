"""URL validation and parsing utilities for batch URL input.

This module provides robust URL validation, markdown link extraction,
and multi-line input parsing for the batch processing UI.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlparse


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ValidationResult:
    """Result of validating a single URL."""
    is_valid: bool
    url: str
    error: Optional[str] = None


@dataclass
class ParseResult:
    """Result of parsing multi-line URL input."""
    valid_urls: List[str] = field(default_factory=list)
    invalid_lines: List[Tuple[int, str, str]] = field(default_factory=list)  # (line_number, content, reason)
    skipped_lines: int = 0
    duplicates_removed: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class SanitizedUrls:
    """Result of sanitizing a list of URLs."""
    urls: List[str] = field(default_factory=list)
    duplicates_removed: int = 0
    warnings: List[str] = field(default_factory=list)


# =============================================================================
# Constants
# =============================================================================

# Regex for extracting URL from markdown link syntax: [text](url)
# 
# LIMITATION: This pattern uses a greedy match for the URL portion which handles
# most URLs including those with parentheses like https://en.wikipedia.org/wiki/Example_(disambiguation).
# However, it may fail on edge cases with nested or unbalanced parentheses in the URL.
# For the batch URL processing use case, this is acceptable since:
# 1. Most news/article URLs don't contain parentheses
# 2. Users can always paste plain URLs without markdown wrapping
# 3. Implementing full balanced-parenthesis parsing adds significant complexity
#
# The pattern matches: [link text](url content until last closing paren)
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]*)\]\((.+)\)$')

# Maximum URLs before warning user about large batch
MAX_URLS_BEFORE_WARNING = 100


# =============================================================================
# URL Extraction Functions
# =============================================================================

def extract_url_from_markdown(text: str) -> Optional[str]:
    """
    Extract URL from markdown link syntax [text](url).
    
    Args:
        text: A string that may contain a markdown link.
        
    Returns:
        The extracted URL if markdown syntax found, None otherwise.
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Check if the text matches markdown link pattern
    match = MARKDOWN_LINK_PATTERN.match(text)
    if match:
        return match.group(2)
    
    return None


# =============================================================================
# URL Validation Functions
# =============================================================================

def validate_url(url: Optional[str]) -> ValidationResult:
    """
    Validate a single URL.
    
    Args:
        url: The URL string to validate.
        
    Returns:
        ValidationResult with is_valid flag and error message if invalid.
    """
    # Handle None input
    if url is None:
        return ValidationResult(
            is_valid=False,
            url="",
            error="URL cannot be None"
        )
    
    # Handle empty string
    if not url or not url.strip():
        return ValidationResult(
            is_valid=False,
            url=url or "",
            error="URL cannot be empty"
        )
    
    url = url.strip()
    
    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return ValidationResult(
            is_valid=False,
            url=url,
            error=f"Failed to parse URL: {e}"
        )
    
    # Check for valid scheme (http/https)
    if not parsed.scheme:
        return ValidationResult(
            is_valid=False,
            url=url,
            error="URL must have a scheme (http:// or https://)"
        )
    
    if parsed.scheme.lower() not in ('http', 'https'):
        return ValidationResult(
            is_valid=False,
            url=url,
            error=f"Invalid URL scheme: {parsed.scheme}. Use http:// or https://"
        )
    
    # Check for valid netloc (domain)
    if not parsed.netloc:
        return ValidationResult(
            is_valid=False,
            url=url,
            error="URL must have a valid domain"
        )
    
    # URL is valid
    return ValidationResult(
        is_valid=True,
        url=url,
        error=None
    )


# =============================================================================
# Input Parsing Functions
# =============================================================================

def _normalize_url_for_dedup(url: str) -> str:
    """
    Normalize URL for deduplication purposes.
    Removes trailing slashes for comparison.
    """
    url = url.rstrip('/')
    return url


def parse_url_input(text: str) -> ParseResult:
    """
    Parse multi-line URL input text.
    
    Handles:
    - Blank lines (skipped)
    - Comment lines starting with # or // (skipped)
    - Markdown-wrapped URLs [text](url)
    - Leading/trailing whitespace
    - Duplicate URL detection
    
    Args:
        text: Multi-line text containing URLs.
        
    Returns:
        ParseResult with valid URLs, invalid lines, and metadata.
    """
    result = ParseResult()
    
    if not text:
        return result
    
    lines = text.split('\n')
    seen_urls: set = set()  # For deduplication (normalized form)
    
    for line_number, line in enumerate(lines, start=1):
        # Strip whitespace
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            result.skipped_lines += 1
            continue
        
        # Skip comment lines
        if stripped.startswith('#') or stripped.startswith('//'):
            result.skipped_lines += 1
            continue
        
        # Try to extract URL from markdown syntax first
        extracted_url = extract_url_from_markdown(stripped)
        url_to_validate = extracted_url if extracted_url else stripped
        
        # Validate the URL
        validation = validate_url(url_to_validate)
        
        if not validation.is_valid:
            result.invalid_lines.append((
                line_number,
                stripped[:100],  # Truncate very long lines
                validation.error or "Invalid URL"
            ))
            continue
        
        # Check for duplicates using normalized form
        normalized = _normalize_url_for_dedup(validation.url)
        if normalized in seen_urls:
            result.duplicates_removed += 1
            continue
        
        seen_urls.add(normalized)
        result.valid_urls.append(validation.url)
    
    # Warn if too many URLs
    if len(result.valid_urls) > MAX_URLS_BEFORE_WARNING:
        result.warnings.append(
            f"Large batch detected: {len(result.valid_urls)} URLs. "
            "Consider processing in smaller batches for better reliability."
        )
    
    return result


# =============================================================================
# Sanitization Functions
# =============================================================================

def sanitize_url_list(urls: List[str]) -> SanitizedUrls:
    """
    Sanitize a list of URLs by removing duplicates.
    
    Args:
        urls: List of URL strings.
        
    Returns:
        SanitizedUrls with deduplicated list and metadata.
    """
    result = SanitizedUrls()
    
    if not urls:
        return result
    
    seen: set = set()
    
    for url in urls:
        normalized = _normalize_url_for_dedup(url)
        
        if normalized in seen:
            result.duplicates_removed += 1
            continue
        
        seen.add(normalized)
        result.urls.append(url)
    
    return result


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'ValidationResult',
    'ParseResult',
    'SanitizedUrls',
    'extract_url_from_markdown',
    'validate_url',
    'parse_url_input',
    'sanitize_url_list',
]
