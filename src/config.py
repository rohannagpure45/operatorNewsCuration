"""Configuration management for the News Curation Agent."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration (required for operation, but optional for startup)
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model to use for summarization",
    )

    # Fact-Checking (optional - gracefully degrades if not provided)
    google_fact_check_api_key: Optional[str] = Field(
        default=None, description="Google Fact Check Tools API key"
    )
    claimbuster_api_key: Optional[str] = Field(
        default=None, description="ClaimBuster API key (optional)"
    )
    newsguard_api_key: Optional[str] = Field(
        default=None, description="NewsGuard API key (optional)"
    )

    # NewsAPI (optional - for article summary fallback)
    newsapi_key: Optional[str] = Field(
        default=None, description="NewsAPI.org API key for article summary fallback"
    )

    # Storage - Firebase
    firebase_credentials_path: Optional[str] = Field(
        default=None, description="Path to Firebase service account JSON"
    )

    # Storage - Supabase (alternative)
    supabase_url: Optional[str] = Field(default=None, description="Supabase project URL")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anon key")

    # Browser automation (optional - uses local Playwright if not set)
    browserless_api_key: Optional[str] = Field(
        default=None, description="Browserless.io API key for cloud browser"
    )
    browserless_use_unblock: bool = Field(
        default=True, description="Enable /unblock API fallback for bot detection bypass"
    )
    browserless_use_residential_proxy: bool = Field(
        default=False, description="Use residential proxy with /unblock API (paid feature)"
    )

    # API Settings
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")

    # Application Settings
    log_level: str = Field(default="INFO", description="Logging level")
    rate_limit: int = Field(default=60, description="Rate limit per minute")
    max_concurrent_requests: int = Field(
        default=10, description="Maximum concurrent URL processing"
    )

    # Timeouts
    extraction_timeout: int = Field(
        default=30, description="Timeout for content extraction in seconds"
    )
    llm_timeout: int = Field(
        default=60, description="Timeout for LLM requests in seconds"
    )

    # Narrative Theming (optional - enhances output framing)
    narrative_theme: str = Field(
        default="abundance",
        description="Narrative theme for content framing: abundance, hope, opportunity, none",
    )
    narrative_enabled: bool = Field(
        default=True,
        description="Enable narrative framing in summaries",
    )
    narrative_subtlety: str = Field(
        default="moderate",
        description="Framing intensity: subtle, moderate, prominent",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def has_firebase(self) -> bool:
        """Check if Firebase is configured."""
        return bool(
            self.firebase_credentials_path
            and os.path.exists(self.firebase_credentials_path)
        )

    @property
    def has_supabase(self) -> bool:
        """Check if Supabase is configured."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def has_storage(self) -> bool:
        """Check if any storage backend is configured."""
        return self.has_firebase or self.has_supabase


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


