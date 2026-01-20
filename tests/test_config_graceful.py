
import os
import pytest
from pydantic import ValidationError

def test_settings_validation_no_api_key():
    """Test that Settings initializes successfully when API key is missing (defaults to None)."""
    # Track state for cleanup
    has_env = False
    original_key = None
    
    try:
        # Backup .env if it exists (inside try so finally can restore it)
        has_env = os.path.exists(".env")
        if has_env:
            os.rename(".env", ".env.tmp")
        
        # Temporarily unset the environment variable if it exists
        original_key = os.environ.get("GEMINI_API_KEY")
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        
        # Use Settings directly to avoid Streamlit secrets interference
        from src.config import Settings
        
        # Now that we fixed it, this should SUCCEED and be None
        settings = Settings()
        assert settings.gemini_api_key is None
        print("\nSettings initialized successfully with None key (Fix verified!)")
    except ValidationError as e:
        pytest.fail(f"Caught ValidationError! Fix did not work. Error: {e}")
    finally:
        # Restore environment variable (use explicit None check to handle empty string)
        if original_key is not None:
            os.environ["GEMINI_API_KEY"] = original_key
        elif "GEMINI_API_KEY" in os.environ:
            # Key wasn't originally set, so remove it if test somehow set it
            del os.environ["GEMINI_API_KEY"]
        
        # Restore .env file
        if has_env and os.path.exists(".env.tmp"):
            os.rename(".env.tmp", ".env")


def test_all_settings_have_defaults():
    """Test that all Settings fields have sensible defaults for Streamlit Cloud deployment."""
    has_env = False
    saved_env = {}
    
    try:
        # Backup .env file
        has_env = os.path.exists(".env")
        if has_env:
            os.rename(".env", ".env.tmp")
        
        # Save and clear all relevant environment variables
        env_prefixes = ('GEMINI', 'GOOGLE', 'BROWSER', 'SUPABASE', 'FIREBASE', 
                        'CLAIMBUSTER', 'NEWSGUARD', 'NEWSAPI', 'API_', 'LOG_', 
                        'RATE_', 'MAX_', 'EXTRACTION_', 'LLM_', 'NARRATIVE_')
        for key in list(os.environ.keys()):
            if any(key.startswith(prefix) for prefix in env_prefixes):
                saved_env[key] = os.environ.pop(key)
        
        # Instantiate Settings directly (get_settings is not cached)
        from src.config import Settings
        settings = Settings()
        
        # Verify key optional fields are None (not raising errors)
        assert settings.gemini_api_key is None
        assert settings.google_fact_check_api_key is None
        assert settings.browserless_api_key is None
        assert settings.firebase_credentials_path is None
        assert settings.supabase_url is None
        
        # Verify fields with defaults work
        assert settings.gemini_model == "gemini-3-flash-preview"
        assert settings.log_level == "INFO"
        assert settings.api_port == 8000
        assert settings.narrative_theme == "abundance"
        
        print("\nAll Settings fields have proper defaults!")
        
    except ValidationError as e:
        pytest.fail(f"Settings failed to initialize with defaults: {e}")
    finally:
        # Restore environment variables
        os.environ.update(saved_env)
        
        # Restore .env file
        if has_env and os.path.exists(".env.tmp"):
            os.rename(".env.tmp", ".env")

