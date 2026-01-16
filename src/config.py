"""Configuration management for the News Curation Agent."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration (required for operation, but optional for startup)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3-flash-preview"

    # Fact-Checking (optional - gracefully degrades if not provided)
    google_fact_check_api_key: Optional[str] = None
    claimbuster_api_key: Optional[str] = None
    newsguard_api_key: Optional[str] = None

    # NewsAPI (optional - for article summary fallback)
    newsapi_key: Optional[str] = None

    # Storage - Firebase
    firebase_credentials_path: Optional[str] = None

    # Storage - Supabase (alternative)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # Browser automation (optional - uses local Playwright if not set)
    browserless_api_key: Optional[str] = None
    browserless_use_unblock: bool = True
    browserless_use_residential_proxy: bool = False

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Application Settings
    log_level: str = "INFO"
    rate_limit: int = 60
    max_concurrent_requests: int = 10

    # Timeouts
    extraction_timeout: int = 30
    llm_timeout: int = 60

    # Narrative Theming (optional - enhances output framing)
    narrative_theme: str = "abundance"
    narrative_enabled: bool = True
    narrative_subtlety: str = "moderate"

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


def get_settings() -> Settings:
    """Get application settings.
    
    Loads settings from environment variables, .env file, and Streamlit secrets.
    Streamlit secrets take priority when running in Streamlit.
    """
    # First, try to get API key from Streamlit secrets
    streamlit_api_key = None
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'GEMINI_API_KEY' in st.secrets:
            streamlit_api_key = st.secrets['GEMINI_API_KEY']
    except Exception:
        # Not running in Streamlit or secrets not available
        pass
    
    # Create settings - if we have a Streamlit secret, use it
    if streamlit_api_key:
        return Settings(gemini_api_key=streamlit_api_key)
    else:
        return Settings()


