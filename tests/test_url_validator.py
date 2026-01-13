"""Tests for URL validation and parsing module.

Crawl Phase: All edge cases defined as tests BEFORE implementation.
These tests will fail until url_validator.py is implemented.
"""

import pytest
from dataclasses import dataclass
from typing import List, Tuple, Optional


# =============================================================================
# Test Data Classes (matching planned implementation)
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
    valid_urls: List[str]
    invalid_lines: List[Tuple[int, str, str]]  # (line_number, content, reason)
    skipped_lines: int
    duplicates_removed: int
    warnings: List[str]


@dataclass
class SanitizedUrls:
    """Result of sanitizing a list of URLs."""
    urls: List[str]
    duplicates_removed: int
    warnings: List[str]


# =============================================================================
# URL Extraction Tests
# =============================================================================

class TestExtractUrlFromMarkdown:
    """Tests for extracting URLs from markdown link syntax."""
    
    def test_extract_url_from_markdown_link_basic(self):
        """Should extract URL from [text](url) format."""
        from src.utils.url_validator import extract_url_from_markdown
        
        text = "[https://example.com](https://example.com)"
        result = extract_url_from_markdown(text)
        
        assert result == "https://example.com"
    
    def test_extract_url_from_markdown_link_with_different_text(self):
        """Should extract URL even if text differs from URL."""
        from src.utils.url_validator import extract_url_from_markdown
        
        text = "[Click Here](https://example.com/article)"
        result = extract_url_from_markdown(text)
        
        assert result == "https://example.com/article"
    
    def test_extract_url_plain_url_no_markdown(self):
        """Should return None for plain URLs (not markdown)."""
        from src.utils.url_validator import extract_url_from_markdown
        
        text = "https://example.com/article"
        result = extract_url_from_markdown(text)
        
        assert result is None
    
    def test_extract_url_from_markdown_with_complex_url(self):
        """Should handle URLs with query params and fragments."""
        from src.utils.url_validator import extract_url_from_markdown
        
        text = "[Link](https://example.com/path?foo=bar&baz=123#section)"
        result = extract_url_from_markdown(text)
        
        assert result == "https://example.com/path?foo=bar&baz=123#section"
    
    def test_extract_url_from_markdown_real_batch_example(self):
        """Should handle real example from batch_urls.txt."""
        from src.utils.url_validator import extract_url_from_markdown
        
        text = "[https://www.vktr.com/ai-news/nvidia-acquires-groq-assets-for-20b/](https://www.vktr.com/ai-news/nvidia-acquires-groq-assets-for-20b/)"
        result = extract_url_from_markdown(text)
        
        assert result == "https://www.vktr.com/ai-news/nvidia-acquires-groq-assets-for-20b/"


# =============================================================================
# URL Validation Tests
# =============================================================================

class TestValidateUrl:
    """Tests for validating individual URLs."""
    
    def test_validate_valid_https_url(self):
        """Should accept valid HTTPS URL."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://example.com/article")
        
        assert result.is_valid is True
        assert result.url == "https://example.com/article"
        assert result.error is None
    
    def test_validate_valid_http_url(self):
        """Should accept valid HTTP URL."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("http://example.com/article")
        
        assert result.is_valid is True
    
    def test_reject_url_without_scheme(self):
        """Should reject URL without http/https scheme."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("example.com/article")
        
        assert result.is_valid is False
        assert "scheme" in result.error.lower() or "http" in result.error.lower()
    
    def test_reject_malformed_url(self):
        """Should reject clearly malformed URLs."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("not-a-url")
        
        assert result.is_valid is False
        assert result.error is not None
    
    def test_reject_empty_url(self):
        """Should reject empty string."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("")
        
        assert result.is_valid is False
    
    def test_reject_scheme_only(self):
        """Should reject URL with scheme only (no host)."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://")
        
        assert result.is_valid is False
    
    def test_accept_url_with_query_params(self):
        """Should accept URL with query parameters."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://example.com?foo=bar&baz=123")
        
        assert result.is_valid is True
    
    def test_accept_url_with_fragment(self):
        """Should accept URL with fragment identifier."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://example.com/article#section-1")
        
        assert result.is_valid is True
    
    def test_accept_url_with_port(self):
        """Should accept URL with port number."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://example.com:8080/path")
        
        assert result.is_valid is True
    
    def test_accept_url_with_encoded_characters(self):
        """Should accept URL with percent-encoded characters."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://example.com/path%20with%20spaces")
        
        assert result.is_valid is True
    
    def test_handle_unicode_in_path(self):
        """Should handle URLs with unicode characters in path."""
        from src.utils.url_validator import validate_url
        
        result = validate_url("https://example.com/日本語")
        
        # Should either accept as-is or encode properly
        assert result.is_valid is True


# =============================================================================
# Parse URL Input Tests (Multi-line)
# =============================================================================

class TestParseUrlInput:
    """Tests for parsing multi-line URL input text."""
    
    def test_parse_empty_input(self):
        """Should return empty result for empty input."""
        from src.utils.url_validator import parse_url_input
        
        result = parse_url_input("")
        
        assert result.valid_urls == []
        assert result.invalid_lines == []
        assert result.skipped_lines == 0
    
    def test_parse_whitespace_only_input(self):
        """Should return empty result for whitespace-only input."""
        from src.utils.url_validator import parse_url_input
        
        result = parse_url_input("   \n\n   \t  \n")
        
        assert result.valid_urls == []
        assert result.skipped_lines >= 3  # At least the blank lines
    
    def test_parse_single_valid_url(self):
        """Should parse single URL correctly."""
        from src.utils.url_validator import parse_url_input
        
        result = parse_url_input("https://example.com/article")
        
        assert result.valid_urls == ["https://example.com/article"]
        assert result.invalid_lines == []
    
    def test_parse_multiple_urls_with_blank_lines(self):
        """Should parse multiple URLs, skipping blank lines."""
        from src.utils.url_validator import parse_url_input
        
        text = """https://example.com/article1

https://example.com/article2
   
https://example.com/article3"""
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 3
        assert result.skipped_lines == 2  # Two blank lines
    
    def test_parse_urls_with_leading_trailing_whitespace(self):
        """Should trim whitespace from URLs."""
        from src.utils.url_validator import parse_url_input
        
        text = """  https://example.com/article1  
   https://example.com/article2"""
        
        result = parse_url_input(text)
        
        assert result.valid_urls == [
            "https://example.com/article1",
            "https://example.com/article2",
        ]
    
    def test_parse_deduplicate_urls(self):
        """Should remove duplicate URLs."""
        from src.utils.url_validator import parse_url_input
        
        text = """https://example.com/article
https://example.com/article
https://example.com/other"""
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 2
        assert result.duplicates_removed == 1
    
    def test_parse_skip_comment_lines_hash(self):
        """Should skip lines starting with #."""
        from src.utils.url_validator import parse_url_input
        
        text = """# This is a comment
https://example.com/article
# Another comment"""
        
        result = parse_url_input(text)
        
        assert result.valid_urls == ["https://example.com/article"]
        assert result.skipped_lines == 2
    
    def test_parse_skip_comment_lines_double_slash(self):
        """Should skip lines starting with //."""
        from src.utils.url_validator import parse_url_input
        
        text = """// This is a comment
https://example.com/article"""
        
        result = parse_url_input(text)
        
        assert result.valid_urls == ["https://example.com/article"]
        assert result.skipped_lines == 1
    
    def test_parse_track_invalid_lines(self):
        """Should track invalid lines with reasons."""
        from src.utils.url_validator import parse_url_input
        
        text = """https://example.com/valid
not-a-url
https://example.com/valid2
another-invalid"""
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 2
        assert len(result.invalid_lines) == 2
        
        # Check invalid line tracking
        invalid_line_numbers = [line[0] for line in result.invalid_lines]
        assert 2 in invalid_line_numbers
        assert 4 in invalid_line_numbers
    
    def test_parse_extract_from_markdown_wrapped_urls(self):
        """Should extract URLs from markdown link syntax."""
        from src.utils.url_validator import parse_url_input
        
        text = """[https://www.vktr.com/ai-news/](https://www.vktr.com/ai-news/)
[https://example.com/article](https://example.com/article)"""
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 2
        assert "https://www.vktr.com/ai-news/" in result.valid_urls
        assert "https://example.com/article" in result.valid_urls
    
    def test_parse_excessive_urls_warning(self):
        """Should warn when too many URLs are provided."""
        from src.utils.url_validator import parse_url_input
        
        # Generate 100+ URLs
        urls = [f"https://example.com/article{i}" for i in range(150)]
        text = "\n".join(urls)
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 150
        assert any("large" in w.lower() or "many" in w.lower() for w in result.warnings)
    
    def test_parse_real_batch_urls_file(self):
        """Should correctly parse content like batch_urls.txt."""
        from src.utils.url_validator import parse_url_input
        
        # Simulating batch_urls.txt content
        text = """[https://www.vktr.com/ai-news/nvidia-acquires-groq-assets-for-20b/](https://www.vktr.com/ai-news/nvidia-acquires-groq-assets-for-20b/)
[https://vertu.com/lifestyle/nvidia-acquires-groq-for-20-billion-in-historic-ai-chip-deal/](https://vertu.com/lifestyle/nvidia-acquires-groq-for-20-billion-in-historic-ai-chip-deal/)
[https://azure.microsoft.com/en-us/blog/introducing-gpt-5-2-in-microsoft-foundry-the-new-standard-for-enterprise-ai/](https://azure.microsoft.com/en-us/blog/introducing-gpt-5-2-in-microsoft-foundry-the-new-standard-for-enterprise-ai/)"""
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 3
        assert result.invalid_lines == []
        assert "vktr.com" in result.valid_urls[0]


# =============================================================================
# Sanitize URL List Tests
# =============================================================================

class TestSanitizeUrlList:
    """Tests for sanitizing a list of URLs."""
    
    def test_sanitize_empty_list(self):
        """Should handle empty list."""
        from src.utils.url_validator import sanitize_url_list
        
        result = sanitize_url_list([])
        
        assert result.urls == []
        assert result.duplicates_removed == 0
    
    def test_sanitize_remove_duplicates(self):
        """Should remove duplicate URLs."""
        from src.utils.url_validator import sanitize_url_list
        
        urls = [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/a",  # duplicate
        ]
        
        result = sanitize_url_list(urls)
        
        assert len(result.urls) == 2
        assert result.duplicates_removed == 1
    
    def test_sanitize_preserve_order(self):
        """Should preserve order of first occurrence."""
        from src.utils.url_validator import sanitize_url_list
        
        urls = [
            "https://example.com/first",
            "https://example.com/second",
            "https://example.com/first",  # duplicate
            "https://example.com/third",
        ]
        
        result = sanitize_url_list(urls)
        
        assert result.urls == [
            "https://example.com/first",
            "https://example.com/second",
            "https://example.com/third",
        ]
    
    def test_sanitize_normalize_trailing_slashes(self):
        """Should treat URLs with/without trailing slash as same."""
        from src.utils.url_validator import sanitize_url_list
        
        urls = [
            "https://example.com/path",
            "https://example.com/path/",  # with trailing slash
        ]
        
        result = sanitize_url_list(urls)
        
        # Should dedupe these as same URL
        assert len(result.urls) == 1


# =============================================================================
# Integration-Style Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def test_full_workflow_with_mixed_input(self):
        """Should handle realistic mixed input with various issues."""
        from src.utils.url_validator import parse_url_input
        
        text = """# AI News Batch - January 2026
[https://www.vktr.com/ai-news/article1/](https://www.vktr.com/ai-news/article1/)
https://www.vktr.com/ai-news/article1/

invalid-line-here
   
https://example.com/valid
// skipped comment
https://example.com/valid2"""
        
        result = parse_url_input(text)
        
        # Should have 3 valid URLs (one duplicate removed)
        assert len(result.valid_urls) == 3
        # Should have 1 invalid line
        assert len(result.invalid_lines) == 1
        # Should have skipped 4 lines (2 comments + 2 blank)
        assert result.skipped_lines == 4
        # Should have removed 1 duplicate
        assert result.duplicates_removed == 1


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling edge cases."""
    
    def test_validate_none_input(self):
        """Should handle None gracefully."""
        from src.utils.url_validator import validate_url
        
        # Should not raise, should return invalid
        result = validate_url(None)
        
        assert result.is_valid is False
    
    def test_parse_very_long_line(self):
        """Should handle extremely long lines."""
        from src.utils.url_validator import parse_url_input
        
        long_url = "https://example.com/" + "a" * 10000
        
        # Should not raise
        result = parse_url_input(long_url)
        
        # May be valid or invalid, but should not crash
        assert isinstance(result.valid_urls, list)
    
    def test_parse_special_characters_in_content(self):
        """Should handle special characters without crashing."""
        from src.utils.url_validator import parse_url_input
        
        text = """https://example.com/valid
<script>alert('xss')</script>
https://example.com/valid2"""
        
        result = parse_url_input(text)
        
        assert len(result.valid_urls) == 2
        assert len(result.invalid_lines) == 1
