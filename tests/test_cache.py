"""Tests for the local cache module.

This test suite covers:
- Cache initialization and directory creation
- Adding, retrieving, and clearing cache entries
- Edge cases: empty cache, corrupted files, unwritable directories
- Entry deduplication and FIFO eviction
- Schema versioning and migration
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "cache"


@pytest.fixture
def sample_entry_data():
    """Sample cache entry data for testing."""
    return {
        "url": "https://example.com/article1",
        "title": "Test Article Title",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc),
        "source_type": "news_article",
    }


@pytest.fixture
def sample_entries_list():
    """Multiple sample entries for testing ordering and limits."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "url": f"https://example.com/article{i}",
            "title": f"Article {i}",
            "status": "completed" if i % 2 == 0 else "failed",
            "timestamp": base_time - timedelta(hours=i),
            "source_type": "news_article",
        }
        for i in range(15)
    ]


# =============================================================================
# Unit Tests for LocalCache
# =============================================================================


class TestCacheInitialization:
    """Tests for cache initialization and directory creation."""

    def test_cache_init_creates_directory(self, temp_cache_dir):
        """Cache should create the cache directory if it doesn't exist."""
        from src.cache.cache import LocalCache
        
        assert not temp_cache_dir.exists()
        cache = LocalCache(cache_dir=temp_cache_dir)
        assert temp_cache_dir.exists()

    def test_cache_init_uses_default_directory(self):
        """Cache should use ~/.newscuration/cache by default."""
        from src.cache.cache import LocalCache
        
        with patch.object(LocalCache, '_get_default_cache_dir') as mock_default:
            mock_default.return_value = Path("/tmp/test_default_cache")
            cache = LocalCache()
            mock_default.assert_called_once()

    def test_cache_init_handles_existing_directory(self, temp_cache_dir):
        """Cache should work with pre-existing directory."""
        from src.cache.cache import LocalCache
        
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache = LocalCache(cache_dir=temp_cache_dir)
        assert temp_cache_dir.exists()


class TestCacheAddEntry:
    """Tests for adding entries to the cache."""

    def test_cache_add_entry_success(self, temp_cache_dir, sample_entry_data):
        """Adding an entry should succeed and persist to file."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entry = CacheEntry(**sample_entry_data)
        
        result = cache.add_entry(entry)
        
        assert result is True
        assert (temp_cache_dir / "history.json").exists()

    def test_cache_add_entry_persists_data(self, temp_cache_dir, sample_entry_data):
        """Added entries should be retrievable after reload."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entry = CacheEntry(**sample_entry_data)
        cache.add_entry(entry)
        
        # Create new cache instance to verify persistence
        cache2 = LocalCache(cache_dir=temp_cache_dir)
        entries = cache2.load()
        
        assert len(entries) == 1
        assert entries[0].url == sample_entry_data["url"]
        assert entries[0].title == sample_entry_data["title"]

    def test_cache_add_multiple_entries(self, temp_cache_dir, sample_entries_list):
        """Multiple entries should all be stored correctly."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        
        for entry_data in sample_entries_list[:5]:
            cache.add_entry(CacheEntry(**entry_data))
        
        entries = cache.load()
        assert len(entries) == 5


class TestCacheGetRecent:
    """Tests for retrieving recent entries."""

    def test_cache_get_recent_respects_limit(self, temp_cache_dir, sample_entries_list):
        """get_recent should return at most 'limit' entries."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        
        for entry_data in sample_entries_list:
            cache.add_entry(CacheEntry(**entry_data))
        
        recent = cache.get_recent(limit=5)
        
        assert len(recent) == 5

    def test_cache_get_recent_ordered_by_timestamp(self, temp_cache_dir, sample_entries_list):
        """get_recent should return entries ordered by timestamp (newest first)."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        
        for entry_data in sample_entries_list:
            cache.add_entry(CacheEntry(**entry_data))
        
        recent = cache.get_recent(limit=10)
        
        # Verify ordering: each entry should be newer than or equal to the next
        for i in range(len(recent) - 1):
            assert recent[i].timestamp >= recent[i + 1].timestamp

    def test_cache_get_recent_with_fewer_entries_than_limit(self, temp_cache_dir, sample_entry_data):
        """get_recent should return all entries if fewer than limit exist."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        cache.add_entry(CacheEntry(**sample_entry_data))
        
        recent = cache.get_recent(limit=10)
        
        assert len(recent) == 1


class TestCacheEdgeCases:
    """Tests for edge cases and error handling."""

    def test_cache_handles_empty_cache(self, temp_cache_dir):
        """Empty cache should return empty list, no errors."""
        from src.cache.cache import LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entries = cache.load()
        recent = cache.get_recent(limit=10)
        
        assert entries == []
        assert recent == []

    def test_cache_handles_corrupted_file(self, temp_cache_dir):
        """Corrupted cache file should be handled gracefully."""
        from src.cache.cache import LocalCache
        
        # Create corrupted file
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = temp_cache_dir / "history.json"
        cache_file.write_text("{ invalid json content }")
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entries = cache.load()
        
        # Should return empty list and not crash
        assert entries == []
        # Backup file should be created
        assert (temp_cache_dir / "history.json.corrupt").exists()

    def test_cache_handles_unwritable_directory(self, temp_cache_dir, sample_entry_data):
        """Unwritable directory should gracefully degrade."""
        from src.cache.cache import CacheEntry, LocalCache
        
        # Create directory and make it read-only
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(temp_cache_dir, 0o444)
        
        try:
            cache = LocalCache(cache_dir=temp_cache_dir)
            entry = CacheEntry(**sample_entry_data)
            result = cache.add_entry(entry)
            
            # Should return False indicating failure
            assert result is False
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_cache_dir, 0o755)


class TestCacheEnforcesLimits:
    """Tests for entry limits and eviction."""

    def test_cache_enforces_max_entries(self, temp_cache_dir):
        """Cache should evict oldest entries when exceeding max."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir, max_entries=5)
        base_time = datetime.now(timezone.utc)
        
        # Add 10 entries
        for i in range(10):
            entry = CacheEntry(
                url=f"https://example.com/article{i}",
                title=f"Article {i}",
                status="completed",
                timestamp=base_time + timedelta(minutes=i),
                source_type="news_article",
            )
            cache.add_entry(entry)
        
        entries = cache.load()
        
        # Should only have 5 entries (the newest ones)
        assert len(entries) == 5
        # Oldest entry should be article5 (first 5 evicted)
        urls = [e.url for e in entries]
        assert "https://example.com/article0" not in urls
        assert "https://example.com/article9" in urls


class TestCacheDeduplication:
    """Tests for URL deduplication."""

    def test_cache_deduplicates_urls(self, temp_cache_dir):
        """Adding same URL twice should update timestamp, not create duplicate."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        
        # Add first entry
        entry1 = CacheEntry(
            url="https://example.com/article",
            title="Original Title",
            status="completed",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
            source_type="news_article",
        )
        cache.add_entry(entry1)
        
        # Add same URL with different timestamp
        entry2 = CacheEntry(
            url="https://example.com/article",
            title="Updated Title",
            status="completed",
            timestamp=datetime.now(timezone.utc),
            source_type="news_article",
        )
        cache.add_entry(entry2)
        
        entries = cache.load()
        
        # Should only have one entry
        assert len(entries) == 1
        # Should have updated title and timestamp
        assert entries[0].title == "Updated Title"

    def test_cache_get_by_url(self, temp_cache_dir, sample_entry_data):
        """Should be able to retrieve a specific entry by URL."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        cache.add_entry(CacheEntry(**sample_entry_data))
        
        entry = cache.get_by_url(sample_entry_data["url"])
        
        assert entry is not None
        assert entry.url == sample_entry_data["url"]

    def test_cache_get_by_url_not_found(self, temp_cache_dir):
        """get_by_url should return None for non-existent URL."""
        from src.cache.cache import LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entry = cache.get_by_url("https://nonexistent.com/article")
        
        assert entry is None


class TestCacheClear:
    """Tests for clearing cache."""

    def test_cache_clears_all_entries(self, temp_cache_dir, sample_entries_list):
        """clear() should remove all entries."""
        from src.cache.cache import CacheEntry, LocalCache
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        
        for entry_data in sample_entries_list[:5]:
            cache.add_entry(CacheEntry(**entry_data))
        
        assert len(cache.load()) == 5
        
        result = cache.clear()
        
        assert result is True
        assert len(cache.load()) == 0


class TestCacheSchemaVersion:
    """Tests for schema versioning and migration."""

    def test_cache_includes_schema_version(self, temp_cache_dir, sample_entry_data):
        """Cache file should include schema version."""
        from src.cache.cache import CacheEntry, LocalCache, CURRENT_SCHEMA_VERSION
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        cache.add_entry(CacheEntry(**sample_entry_data))
        
        cache_file = temp_cache_dir / "history.json"
        with open(cache_file) as f:
            data = json.load(f)
        
        assert "version" in data
        assert data["version"] == CURRENT_SCHEMA_VERSION

    def test_cache_schema_version_migration(self, temp_cache_dir):
        """Old schema versions should trigger migration."""
        from src.cache.cache import LocalCache
        
        # Create cache file with old version
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = temp_cache_dir / "history.json"
        old_data = {
            "version": 0,
            "entries": [
                {
                    "url": "https://example.com/old",
                    "status": "completed",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
        }
        with open(cache_file, "w") as f:
            json.dump(old_data, f)
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entries = cache.load()
        
        # Should handle migration (exact behavior depends on implementation)
        # For now, just verify it doesn't crash
        assert isinstance(entries, list)

    def test_cache_schema_v1_to_v2_migration(self, temp_cache_dir):
        """Version 1 schema should migrate to version 2 with result_json field."""
        from src.cache.cache import LocalCache
        
        # Create cache file with v1 schema (no result_json field)
        temp_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = temp_cache_dir / "history.json"
        v1_data = {
            "version": 1,
            "entries": [
                {
                    "url": "https://example.com/v1",
                    "title": "Test Article",
                    "status": "completed",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "source_type": "news_article",
                }
            ],
        }
        with open(cache_file, "w") as f:
            json.dump(v1_data, f)
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        entries = cache.load()
        
        # Should have migrated successfully
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/v1"
        # result_json should exist and be None (added by migration)
        assert hasattr(entries[0], 'result_json')
        assert entries[0].result_json is None


# =============================================================================
# Integration Tests
# =============================================================================


class TestCachePersistence:
    """Integration tests for cache persistence across sessions."""

    def test_cache_persists_across_sessions(self, temp_cache_dir, sample_entries_list):
        """Cache data should persist across multiple cache instances."""
        from src.cache.cache import CacheEntry, LocalCache
        
        # Session 1: Add entries
        cache1 = LocalCache(cache_dir=temp_cache_dir)
        for entry_data in sample_entries_list[:3]:
            cache1.add_entry(CacheEntry(**entry_data))
        
        # Session 2: Read entries
        cache2 = LocalCache(cache_dir=temp_cache_dir)
        entries = cache2.load()
        
        assert len(entries) == 3
        
        # Session 3: Add more entries
        cache3 = LocalCache(cache_dir=temp_cache_dir)
        for entry_data in sample_entries_list[3:5]:
            cache3.add_entry(CacheEntry(**entry_data))
        
        # Final verification
        cache4 = LocalCache(cache_dir=temp_cache_dir)
        entries = cache4.load()
        
        assert len(entries) == 5


class TestCacheFileLocking:
    """Tests for concurrent access handling."""

    def test_cache_handles_concurrent_writes(self, temp_cache_dir):
        """Cache should handle concurrent writes via file locking."""
        from src.cache.cache import CacheEntry, LocalCache
        import threading
        
        cache = LocalCache(cache_dir=temp_cache_dir)
        errors = []
        
        def add_entry(i):
            try:
                entry = CacheEntry(
                    url=f"https://example.com/concurrent{i}",
                    title=f"Concurrent Article {i}",
                    status="completed",
                    timestamp=datetime.now(timezone.utc),
                    source_type="news_article",
                )
                cache.add_entry(entry)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads to simulate concurrent access
        threads = [threading.Thread(target=add_entry, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should not have any errors
        assert len(errors) == 0
        
        # All entries should be in cache (may be fewer if dedup kicks in)
        entries = cache.load()
        assert len(entries) == 10
