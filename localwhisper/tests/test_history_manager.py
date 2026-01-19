"""
Tests for History Manager
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from localwhisper.core.history_manager import (
    HistoryManager,
    HistoryEntry,
    HistorySettings,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_history.db"
        yield db_path


@pytest.fixture
def history_manager(temp_db):
    """Create a HistoryManager with temporary database."""
    manager = HistoryManager(db_path=temp_db)
    manager.initialize()
    yield manager
    manager.shutdown()


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        entry = HistoryEntry(
            id=1,
            text="Hello world",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            duration=2.5,
            confidence=0.95,
            language="en",
            model="turbo",
        )
        result = entry.to_dict()

        assert result["id"] == 1
        assert result["text"] == "Hello world"
        assert result["duration"] == 2.5
        assert result["confidence"] == 0.95
        assert result["language"] == "en"
        assert result["model"] == "turbo"
        assert "2024-01-15" in result["timestamp"]

    def test_from_row(self):
        """Should create from database row."""
        row = (1, "Test text", "2024-01-15T10:30:00", 3.0, 0.9, "en", "turbo")
        entry = HistoryEntry.from_row(row)

        assert entry.id == 1
        assert entry.text == "Test text"
        assert entry.duration == 3.0
        assert entry.confidence == 0.9
        assert entry.language == "en"
        assert entry.model == "turbo"


class TestHistoryManager:
    """Tests for HistoryManager class."""

    def test_add_entry(self, history_manager):
        """Should add entry to database."""
        entry = history_manager.add_entry(
            text="Test transcription",
            duration=2.5,
            confidence=0.95,
            language="en",
            model="turbo",
        )

        assert entry.id is not None
        assert entry.text == "Test transcription"
        assert entry.duration == 2.5

    def test_get_entry(self, history_manager):
        """Should retrieve entry by ID."""
        entry = history_manager.add_entry(
            text="Test",
            duration=1.0,
            confidence=0.9,
            language="en",
            model="turbo",
        )

        retrieved = history_manager.get_entry(entry.id)
        assert retrieved is not None
        assert retrieved.text == "Test"
        assert retrieved.id == entry.id

    def test_get_entry_not_found(self, history_manager):
        """Should return None for non-existent ID."""
        result = history_manager.get_entry(99999)
        assert result is None

    def test_get_recent(self, history_manager):
        """Should retrieve recent entries in order."""
        for i in range(5):
            history_manager.add_entry(
                text=f"Entry {i}",
                duration=1.0,
                confidence=0.9,
                language="en",
                model="turbo",
            )

        entries = history_manager.get_recent(limit=3)
        assert len(entries) == 3
        # Should be in reverse chronological order
        assert "Entry 4" in entries[0].text

    def test_search(self, history_manager):
        """Should search entries by text."""
        history_manager.add_entry(
            text="The quick brown fox",
            duration=1.0,
            confidence=0.9,
            language="en",
            model="turbo",
        )
        history_manager.add_entry(
            text="Lazy dog",
            duration=1.0,
            confidence=0.9,
            language="en",
            model="turbo",
        )

        results = history_manager.search("fox")
        assert len(results) == 1
        assert "fox" in results[0].text

    def test_delete_entry(self, history_manager):
        """Should delete entry."""
        entry = history_manager.add_entry(
            text="To delete",
            duration=1.0,
            confidence=0.9,
            language="en",
            model="turbo",
        )

        result = history_manager.delete_entry(entry.id)
        assert result is True

        retrieved = history_manager.get_entry(entry.id)
        assert retrieved is None

    def test_delete_nonexistent(self, history_manager):
        """Should return False for non-existent entry."""
        result = history_manager.delete_entry(99999)
        assert result is False

    def test_get_statistics(self, history_manager):
        """Should return statistics."""
        history_manager.add_entry(
            text="Test 1",
            duration=2.5,
            confidence=0.9,
            language="en",
            model="turbo",
        )
        history_manager.add_entry(
            text="Test 2",
            duration=3.5,
            confidence=0.8,
            language="en",
            model="turbo",
        )

        stats = history_manager.get_statistics()

        assert stats["total_entries"] == 2
        assert stats["total_duration_seconds"] == 6.0
        assert stats["average_confidence"] == pytest.approx(0.85, rel=0.01)
        assert "total_duration_formatted" in stats

    def test_clear_all(self, history_manager):
        """Should clear all entries."""
        for i in range(3):
            history_manager.add_entry(
                text=f"Entry {i}",
                duration=1.0,
                confidence=0.9,
                language="en",
                model="turbo",
            )

        deleted = history_manager.clear_all()
        assert deleted == 3

        entries = history_manager.get_recent()
        assert len(entries) == 0

    def test_export_to_json(self, history_manager, temp_db):
        """Should export to JSON."""
        history_manager.add_entry(
            text="Export test",
            duration=1.0,
            confidence=0.9,
            language="en",
            model="turbo",
        )

        export_path = temp_db.parent / "export.json"
        count = history_manager.export_to_json(export_path)

        assert count == 1
        assert export_path.exists()

        import json
        with open(export_path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["text"] == "Export test"

    def test_context_manager(self, temp_db):
        """Should work as context manager."""
        with HistoryManager(db_path=temp_db) as manager:
            manager.add_entry(
                text="Context test",
                duration=1.0,
                confidence=0.9,
                language="en",
                model="turbo",
            )

        # Should be able to reopen
        with HistoryManager(db_path=temp_db) as manager:
            entries = manager.get_recent()
            assert len(entries) == 1


class TestHistoryManagerDisabled:
    """Tests for disabled history."""

    def test_disabled_history(self, temp_db):
        """Should not store when disabled."""
        settings = HistorySettings(enabled=False)
        manager = HistoryManager(settings=settings, db_path=temp_db)
        manager.initialize()

        entry = manager.add_entry(
            text="Should not store",
            duration=1.0,
            confidence=0.9,
            language="en",
            model="turbo",
        )

        # Entry returned but not stored
        assert entry.text == "Should not store"
        assert entry.id is None

        manager.shutdown()
