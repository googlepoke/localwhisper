"""
History Manager for LocalWhisper

Handles storage and retrieval of transcription history using SQLite.
Supports full-text search and automatic cleanup of old entries.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from localwhisper.core.config import HistorySettings, get_data_dir


@dataclass
class HistoryEntry:
    """A single transcription history entry."""
    id: Optional[int]
    text: str
    timestamp: datetime
    duration: float  # Audio duration in seconds
    confidence: float
    language: str
    model: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "confidence": self.confidence,
            "language": self.language,
            "model": self.model,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "HistoryEntry":
        """Create from database row."""
        return cls(
            id=row[0],
            text=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            duration=row[3],
            confidence=row[4],
            language=row[5],
            model=row[6],
        )


class HistoryManager:
    """
    Manages transcription history with SQLite storage.

    Features:
    - Full-text search using SQLite FTS5
    - Automatic cleanup of old entries
    - Export to various formats
    - Statistics and analytics
    """

    def __init__(self, settings: Optional[HistorySettings] = None, db_path: Optional[Path] = None):
        """
        Initialize the history manager.

        Args:
            settings: History configuration settings
            db_path: Custom database path (default: standard app data location)
        """
        self.settings = settings or HistorySettings()
        self._db_path = db_path or (get_data_dir() / "history.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[sqlite3.Connection] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the database and create tables if needed."""
        if self._initialized:
            return

        self._connection = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )

        # Enable WAL mode for better concurrent access
        self._connection.execute("PRAGMA journal_mode=WAL")

        # Create main table
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration REAL NOT NULL,
                confidence REAL NOT NULL,
                language TEXT NOT NULL,
                model TEXT NOT NULL
            )
        """)

        # Create FTS virtual table for full-text search
        self._connection.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
                text,
                content='history',
                content_rowid='id'
            )
        """)

        # Create triggers to keep FTS in sync
        self._connection.execute("""
            CREATE TRIGGER IF NOT EXISTS history_ai AFTER INSERT ON history BEGIN
                INSERT INTO history_fts(rowid, text) VALUES (new.id, new.text);
            END
        """)

        self._connection.execute("""
            CREATE TRIGGER IF NOT EXISTS history_ad AFTER DELETE ON history BEGIN
                INSERT INTO history_fts(history_fts, rowid, text)
                VALUES('delete', old.id, old.text);
            END
        """)

        self._connection.execute("""
            CREATE TRIGGER IF NOT EXISTS history_au AFTER UPDATE ON history BEGIN
                INSERT INTO history_fts(history_fts, rowid, text)
                VALUES('delete', old.id, old.text);
                INSERT INTO history_fts(rowid, text) VALUES (new.id, new.text);
            END
        """)

        # Create index on timestamp for efficient cleanup
        self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)
        """)

        self._connection.commit()
        self._initialized = True

        # Run cleanup on initialization
        if self.settings.enabled:
            self.cleanup_old_entries()

    def shutdown(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        self._initialized = False

    @contextmanager
    def _get_cursor(self):
        """Get a database cursor with automatic commit/rollback."""
        if not self._initialized:
            self.initialize()

        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

    def add_entry(
        self,
        text: str,
        duration: float,
        confidence: float,
        language: str,
        model: str,
        timestamp: Optional[datetime] = None,
    ) -> HistoryEntry:
        """
        Add a new transcription to history.

        Args:
            text: Transcribed text
            duration: Audio duration in seconds
            confidence: Transcription confidence (0-1)
            language: Detected language code
            model: Model used for transcription
            timestamp: Optional custom timestamp (default: now)

        Returns:
            The created HistoryEntry
        """
        if not self.settings.enabled:
            return HistoryEntry(
                id=None,
                text=text,
                timestamp=timestamp or datetime.now(),
                duration=duration,
                confidence=confidence,
                language=language,
                model=model,
            )

        ts = timestamp or datetime.now()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO history (text, timestamp, duration, confidence, language, model)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (text, ts.isoformat(), duration, confidence, language, model),
            )
            entry_id = cursor.lastrowid

        return HistoryEntry(
            id=entry_id,
            text=text,
            timestamp=ts,
            duration=duration,
            confidence=confidence,
            language=language,
            model=model,
        )

    def get_entry(self, entry_id: int) -> Optional[HistoryEntry]:
        """
        Get a specific history entry by ID.

        Args:
            entry_id: The entry ID

        Returns:
            HistoryEntry or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM history WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()

        if row:
            return HistoryEntry.from_row(row)
        return None

    def get_recent(self, limit: int = 50, offset: int = 0) -> List[HistoryEntry]:
        """
        Get recent history entries.

        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of HistoryEntry objects
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM history
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()

        return [HistoryEntry.from_row(row) for row in rows]

    def search(self, query: str, limit: int = 50) -> List[HistoryEntry]:
        """
        Search history using full-text search.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching HistoryEntry objects
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT history.*
                FROM history
                JOIN history_fts ON history.id = history_fts.rowid
                WHERE history_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            rows = cursor.fetchall()

        return [HistoryEntry.from_row(row) for row in rows]

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[HistoryEntry]:
        """
        Get entries within a date range.

        Args:
            start_date: Start of range
            end_date: End of range
            limit: Maximum number of results

        Returns:
            List of HistoryEntry objects
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM history
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (start_date.isoformat(), end_date.isoformat(), limit),
            )
            rows = cursor.fetchall()

        return [HistoryEntry.from_row(row) for row in rows]

    def delete_entry(self, entry_id: int) -> bool:
        """
        Delete a history entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0

    def cleanup_old_entries(self) -> int:
        """
        Delete entries older than retention period.

        Returns:
            Number of entries deleted
        """
        if self.settings.retention_days <= 0:
            return 0

        cutoff = datetime.now() - timedelta(days=self.settings.retention_days)

        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM history WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            return cursor.rowcount

    def enforce_max_entries(self) -> int:
        """
        Delete oldest entries if over max_entries limit.

        Returns:
            Number of entries deleted
        """
        if self.settings.max_entries <= 0:
            return 0

        with self._get_cursor() as cursor:
            # Get current count
            cursor.execute("SELECT COUNT(*) FROM history")
            count = cursor.fetchone()[0]

            if count <= self.settings.max_entries:
                return 0

            # Delete oldest entries
            to_delete = count - self.settings.max_entries
            cursor.execute(
                """
                DELETE FROM history
                WHERE id IN (
                    SELECT id FROM history
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
                """,
                (to_delete,),
            )
            return cursor.rowcount

    def get_statistics(self) -> dict:
        """
        Get statistics about the history.

        Returns:
            Dictionary with statistics
        """
        with self._get_cursor() as cursor:
            # Total entries
            cursor.execute("SELECT COUNT(*) FROM history")
            total = cursor.fetchone()[0]

            # Total duration
            cursor.execute("SELECT SUM(duration) FROM history")
            total_duration = cursor.fetchone()[0] or 0

            # Average confidence
            cursor.execute("SELECT AVG(confidence) FROM history")
            avg_confidence = cursor.fetchone()[0] or 0

            # Entries today
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute(
                "SELECT COUNT(*) FROM history WHERE timestamp >= ?",
                (today.isoformat(),),
            )
            today_count = cursor.fetchone()[0]

            # Most used language
            cursor.execute(
                """
                SELECT language, COUNT(*) as cnt
                FROM history
                GROUP BY language
                ORDER BY cnt DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            most_used_language = row[0] if row else None

        return {
            "total_entries": total,
            "total_duration_seconds": total_duration,
            "total_duration_formatted": self._format_duration(total_duration),
            "average_confidence": round(avg_confidence, 3),
            "entries_today": today_count,
            "most_used_language": most_used_language,
        }

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def export_to_json(self, filepath: Path) -> int:
        """
        Export history to JSON file.

        Args:
            filepath: Output file path

        Returns:
            Number of entries exported
        """
        entries = self.get_recent(limit=self.settings.max_entries)
        data = [entry.to_dict() for entry in entries]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return len(entries)

    def export_to_txt(self, filepath: Path) -> int:
        """
        Export history to plain text file.

        Args:
            filepath: Output file path

        Returns:
            Number of entries exported
        """
        entries = self.get_recent(limit=self.settings.max_entries)

        with open(filepath, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(f"[{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]\n")
                f.write(f"{entry.text}\n")
                f.write(f"---\n\n")

        return len(entries)

    def export_to_csv(self, filepath: Path) -> int:
        """
        Export history to CSV file.

        Args:
            filepath: Output file path

        Returns:
            Number of entries exported
        """
        import csv

        entries = self.get_recent(limit=self.settings.max_entries)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "text", "timestamp", "duration", "confidence", "language", "model"])

            for entry in entries:
                writer.writerow([
                    entry.id,
                    entry.text,
                    entry.timestamp.isoformat(),
                    entry.duration,
                    entry.confidence,
                    entry.language,
                    entry.model,
                ])

        return len(entries)

    def clear_all(self) -> int:
        """
        Delete all history entries.

        Returns:
            Number of entries deleted
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM history")
            return cursor.rowcount

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
        return False
