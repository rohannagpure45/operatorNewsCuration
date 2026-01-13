"""Local cache implementation for persistent history storage.

Provides file-based JSON storage for recent URL processing history with:
- Thread-safe file access via filelock
- Schema versioning for future migrations
- FIFO eviction when exceeding max entries
- Graceful degradation on file system errors
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default constants
DEFAULT_MAX_ENTRIES = 100
CACHE_FILENAME = "history.json"
CURRENT_SCHEMA_VERSION = 1


class CacheEntry(BaseModel):
    """A cached history entry for recent URLs."""

    url: str = Field(description="Processed URL")
    title: Optional[str] = Field(default=None, description="Article title if available")
    status: str = Field(description="Processing status: completed, failed")
    timestamp: datetime = Field(description="When the URL was processed")
    source_type: Optional[str] = Field(default=None, description="URL type")


class CacheData(BaseModel):
    """Schema for the cache file."""

    version: int = Field(default=CURRENT_SCHEMA_VERSION, description="Schema version")
    entries: List[CacheEntry] = Field(default_factory=list, description="Cached entries")


class LocalCache:
    """File-based local cache for URL processing history.
    
    Stores history in ~/.newscuration/cache/history.json by default.
    Uses filelock for process-safe concurrent access.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        """Initialize the local cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.newscuration/cache
            max_entries: Maximum number of entries to keep. Oldest are evicted first.
        """
        self.cache_dir = cache_dir or self._get_default_cache_dir()
        self.max_entries = max_entries
        self._cache_file = self.cache_dir / CACHE_FILENAME
        self._lock_file = self.cache_dir / f"{CACHE_FILENAME}.lock"
        self._writable = True
        
        # Ensure cache directory exists
        self._ensure_directory()

    @staticmethod
    def _get_default_cache_dir() -> Path:
        """Get the default cache directory path."""
        return Path.home() / ".newscuration" / "cache"

    def _ensure_directory(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Cannot create cache directory {self.cache_dir}: {e}")
            self._writable = False

    def _get_lock(self):
        """Get a file lock for thread-safe access."""
        try:
            from filelock import FileLock
            return FileLock(str(self._lock_file), timeout=10)
        except ImportError:
            logger.warning("filelock not installed, file locking disabled")
            return _DummyLock()

    def _load_unlocked(self) -> List[CacheEntry]:
        """Load entries without acquiring lock (for internal use).
        
        Returns:
            List of cache entries, or empty list if cache is empty/invalid.
        """
        if not self._cache_file.exists():
            return []

        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate and migrate schema
            cache_data = self._parse_and_migrate(data)
            return cache_data.entries
                
        except json.JSONDecodeError as e:
            logger.warning(f"Cache file corrupted: {e}")
            self._backup_corrupt_file()
            return []
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            return []

    def _save_unlocked(self, entries: List[CacheEntry]) -> bool:
        """Save entries without acquiring lock (for internal use).
        
        Args:
            entries: List of entries to save
            
        Returns:
            True if save succeeded, False otherwise
        """
        if not self._writable:
            return False

        try:
            cache_data = CacheData(entries=entries)
            
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    cache_data.model_dump(mode="json"),
                    f,
                    indent=2,
                    default=str,
                )
            return True
            
        except OSError as e:
            logger.warning(f"Cannot write to cache file: {e}")
            self._writable = False
            return False
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")
            return False

    def load(self) -> List[CacheEntry]:
        """Load all entries from the cache file.
        
        Returns:
            List of cache entries, or empty list if cache is empty/invalid.
        """
        try:
            with self._get_lock():
                return self._load_unlocked()
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            return []

    def _parse_and_migrate(self, data: dict) -> CacheData:
        """Parse cache data and migrate if needed.
        
        Args:
            data: Raw dictionary from cache file
            
        Returns:
            Validated CacheData object
        """
        version = data.get("version", 0)
        
        if version < CURRENT_SCHEMA_VERSION:
            logger.info(f"Migrating cache from version {version} to {CURRENT_SCHEMA_VERSION}")
            data = self._migrate_schema(data, version)
        
        # Parse entries with validation
        entries = []
        for entry_data in data.get("entries", []):
            try:
                # Handle timestamp parsing
                if isinstance(entry_data.get("timestamp"), str):
                    entry_data["timestamp"] = datetime.fromisoformat(
                        entry_data["timestamp"].replace("Z", "+00:00")
                    )
                entries.append(CacheEntry(**entry_data))
            except Exception as e:
                logger.warning(f"Skipping invalid cache entry: {e}")
                continue
        
        return CacheData(version=CURRENT_SCHEMA_VERSION, entries=entries)

    def _migrate_schema(self, data: dict, from_version: int) -> dict:
        """Migrate schema from older versions.
        
        Args:
            data: Raw cache data
            from_version: Source schema version
            
        Returns:
            Migrated data dict
        """
        # Version 0 -> 1: Add source_type field with default
        if from_version == 0:
            for entry in data.get("entries", []):
                if "source_type" not in entry:
                    entry["source_type"] = None
                if "title" not in entry:
                    entry["title"] = None
            data["version"] = 1
        
        return data

    def _backup_corrupt_file(self) -> None:
        """Backup a corrupted cache file."""
        if self._cache_file.exists():
            backup_path = self._cache_file.with_suffix(".json.corrupt")
            try:
                self._cache_file.rename(backup_path)
                logger.info(f"Backed up corrupt cache to {backup_path}")
            except OSError as e:
                logger.warning(f"Could not backup corrupt cache: {e}")

    def save(self, entries: List[CacheEntry]) -> bool:
        """Save entries to the cache file.
        
        Args:
            entries: List of entries to save
            
        Returns:
            True if save succeeded, False otherwise
        """
        try:
            with self._get_lock():
                return self._save_unlocked(entries)
        except OSError as e:
            logger.warning(f"Cannot write to cache file: {e}")
            self._writable = False
            return False
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")
            return False

    def add_entry(self, entry: CacheEntry) -> bool:
        """Add an entry to the cache.
        
        If the URL already exists, updates the existing entry.
        Enforces max_entries limit via FIFO eviction.
        
        Args:
            entry: Cache entry to add
            
        Returns:
            True if add succeeded, False otherwise
        """
        if not self._writable:
            return False

        try:
            with self._get_lock():
                entries = self._load_unlocked()
                
                # Check for existing entry with same URL
                existing_idx = None
                for i, e in enumerate(entries):
                    if e.url == entry.url:
                        existing_idx = i
                        break
                
                if existing_idx is not None:
                    # Update existing entry
                    entries[existing_idx] = entry
                else:
                    # Add new entry
                    entries.append(entry)
                
                # Sort by timestamp (newest first) and enforce limit
                entries.sort(key=lambda e: e.timestamp, reverse=True)
                entries = entries[: self.max_entries]
                
                return self._save_unlocked(entries)
                
        except Exception as e:
            logger.warning(f"Error adding cache entry: {e}")
            return False

    def get_recent(self, limit: int = 10) -> List[CacheEntry]:
        """Get the most recent entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of most recent entries, ordered by timestamp (newest first)
        """
        entries = self.load()
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def get_by_url(self, url: str) -> Optional[CacheEntry]:
        """Get a specific entry by URL.
        
        Args:
            url: The URL to look up
            
        Returns:
            The cache entry if found, None otherwise
        """
        entries = self.load()
        for entry in entries:
            if entry.url == url:
                return entry
        return None

    def clear(self) -> bool:
        """Clear all entries from the cache.
        
        Returns:
            True if clear succeeded, False otherwise
        """
        return self.save([])


class _DummyLock:
    """Dummy context manager when filelock is not available."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
