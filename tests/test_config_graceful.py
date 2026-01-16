
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
        
        # Clear the lru_cache of get_settings to force reload
        from src.config import get_settings
        get_settings.cache_clear()
        
        # Now that we fixed it, this should SUCCEED and be None
        settings = get_settings()
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
