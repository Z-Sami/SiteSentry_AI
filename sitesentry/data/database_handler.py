"""
Database handler for SiteSentry.

SQLite3-based persistence for scan sessions, wall measurements, socket detections,
and sync queue for offline buffering.
"""

import logging
import sqlite3
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from sitesentry import config

logger = logging.getLogger(__name__)


@dataclass
class WallScanRecord:
    """Wall scan measurement record."""
    session_id: int
    room_id: str
    x: float
    y: float
    d1: float  # lower sensor distance
    d2: float  # upper sensor distance
    alpha: float  # tilt angle
    theta_final: float  # computed wall tilt
    is_critical: bool
    timestamp: float


@dataclass
class SocketScanRecord:
    """Socket detection record."""
    session_id: int
    room_id: str
    socket_id: str
    status: str  # "MATCH", "MISSING", "EXTRA"
    detected_x: float
    detected_y: float
    cad_x: float
    cad_y: float
    confidence: float
    image_path: str
    timestamp: float


class DatabaseHandler:
    """
    SQLite3 database manager for SiteSentry.

    Manages scan sessions, wall scans, socket detections, and sync queue.
    All write operations automatically add records to sync_queue for later upload.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize database handler.

        Creates database file and schema if it doesn't exist.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path or str(config.DATABASE_PATH)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connection = None
        self.cursor = None

        self._init_database()

    def _init_database(self) -> None:
        """Create database connection and initialize schema."""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.connection.cursor()

            # Enable foreign keys
            self.cursor.execute("PRAGMA foreign_keys = ON")

            # Create tables if they don't exist
            self._create_schema()

            self.logger.info(f"Database initialized: {self.db_path}")

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def _create_schema(self) -> None:
        """Create database schema (tables and indexes)."""
        try:
            # Scan sessions table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    room_id TEXT,
                    total_area REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Wall scans table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS wall_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    room_id TEXT NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    d1 REAL NOT NULL,
                    d2 REAL NOT NULL,
                    alpha REAL NOT NULL,
                    theta_final REAL NOT NULL,
                    is_critical BOOLEAN NOT NULL,
                    timestamp REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES scan_sessions(id)
                )
            """)

            # Socket scans table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS socket_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    room_id TEXT NOT NULL,
                    socket_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detected_x REAL NOT NULL,
                    detected_y REAL NOT NULL,
                    cad_x REAL NOT NULL,
                    cad_y REAL NOT NULL,
                    confidence REAL NOT NULL,
                    image_path TEXT,
                    timestamp REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES scan_sessions(id)
                )
            """)

            # Sync queue table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    synced BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    synced_at TEXT
                )
            """)

            # Create indexes
            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wall_scans_session
                ON wall_scans(session_id)
            """)

            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_socket_scans_session
                ON socket_scans(session_id)
            """)

            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_queue_synced
                ON sync_queue(synced)
            """)

            self.connection.commit()
            self.logger.debug("Database schema created")

        except Exception as e:
            self.logger.error(f"Failed to create schema: {e}")
            raise

    def create_scan_session(self, room_id: str = None, total_area: float = None) -> int:
        """
        Create a new scan session.

        Args:
            room_id: Room identifier (optional).
            total_area: Total area scanned in square meters (optional).

        Returns:
            Session ID.
        """
        try:
            timestamp = time.time()
            self.cursor.execute("""
                INSERT INTO scan_sessions (timestamp, room_id, total_area)
                VALUES (?, ?, ?)
            """, (timestamp, room_id, total_area))

            self.connection.commit()
            session_id = self.cursor.lastrowid

            self.logger.info(f"Created scan session {session_id}")
            return session_id

        except Exception as e:
            self.logger.error(f"Failed to create scan session: {e}")
            raise

    def save_wall_scan(self, record: WallScanRecord) -> int:
        """
        Save wall scan result to database.

        Automatically adds record to sync_queue.

        Args:
            record: WallScanRecord object.

        Returns:
            Record ID.
        """
        try:
            self.cursor.execute("""
                INSERT INTO wall_scans
                (session_id, room_id, x, y, d1, d2, alpha, theta_final, is_critical, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (record.session_id, record.room_id, record.x, record.y,
                  record.d1, record.d2, record.alpha, record.theta_final,
                  int(record.is_critical), record.timestamp))

            self.connection.commit()
            record_id = self.cursor.lastrowid

            # Add to sync queue
            self._add_to_sync_queue("wall_scans", record_id)

            self.logger.debug(f"Saved wall scan {record_id}")
            return record_id

        except Exception as e:
            self.logger.error(f"Failed to save wall scan: {e}")
            raise

    def save_socket_scan(self, record: SocketScanRecord) -> int:
        """
        Save socket scan result to database.

        Automatically adds record to sync_queue.

        Args:
            record: SocketScanRecord object.

        Returns:
            Record ID.
        """
        try:
            self.cursor.execute("""
                INSERT INTO socket_scans
                (session_id, room_id, socket_id, status, detected_x, detected_y,
                 cad_x, cad_y, confidence, image_path, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (record.session_id, record.room_id, record.socket_id, record.status,
                  record.detected_x, record.detected_y, record.cad_x, record.cad_y,
                  record.confidence, record.image_path, record.timestamp))

            self.connection.commit()
            record_id = self.cursor.lastrowid

            # Add to sync queue
            self._add_to_sync_queue("socket_scans", record_id)

            self.logger.debug(f"Saved socket scan {record_id}")
            return record_id

        except Exception as e:
            self.logger.error(f"Failed to save socket scan: {e}")
            raise

    def get_unsynced_records(self) -> List[Dict[str, Any]]:
        """
        Get all unsynced records from sync queue.

        Returns:
            List of dictionaries with table_name, record_id, and record data.
        """
        try:
            # Get unsynced queue entries
            self.cursor.execute("""
                SELECT id, table_name, record_id FROM sync_queue WHERE synced = 0
            """)

            queue_records = self.cursor.fetchall()
            results = []

            for queue_id, table_name, record_id in queue_records:
                # Fetch the actual record from the appropriate table
                if table_name == "wall_scans":
                    self.cursor.execute(
                        "SELECT * FROM wall_scans WHERE id = ?", (record_id,)
                    )
                elif table_name == "socket_scans":
                    self.cursor.execute(
                        "SELECT * FROM socket_scans WHERE id = ?", (record_id,)
                    )
                else:
                    continue

                columns = [description[0] for description in self.cursor.description]
                row = self.cursor.fetchone()

                if row:
                    record_dict = dict(zip(columns, row))
                    record_dict["queue_id"] = queue_id
                    record_dict["table_name"] = table_name
                    results.append(record_dict)

            self.logger.debug(f"Found {len(results)} unsynced records")
            return results

        except Exception as e:
            self.logger.error(f"Failed to get unsynced records: {e}")
            return []

    def mark_synced(self, queue_ids: List[int]) -> bool:
        """
        Mark records as synced.

        Args:
            queue_ids: List of sync_queue IDs to mark as synced.

        Returns:
            True if successful, False otherwise.
        """
        try:
            now = datetime.utcnow().isoformat()
            for queue_id in queue_ids:
                self.cursor.execute("""
                    UPDATE sync_queue SET synced = 1, synced_at = ?
                    WHERE id = ?
                """, (now, queue_id))

            self.connection.commit()
            self.logger.debug(f"Marked {len(queue_ids)} records as synced")
            return True

        except Exception as e:
            self.logger.error(f"Failed to mark synced: {e}")
            return False

    def get_session_summary(self, session_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for a scan session.

        Args:
            session_id: Session ID.

        Returns:
            Dictionary with session statistics.
        """
        try:
            self.cursor.execute("""
                SELECT id, timestamp, room_id, total_area FROM scan_sessions WHERE id = ?
            """, (session_id,))

            session = self.cursor.fetchone()
            if not session:
                return {}

            # Count wall scans
            self.cursor.execute("""
                SELECT COUNT(*) as total, SUM(is_critical) as critical
                FROM wall_scans WHERE session_id = ?
            """, (session_id,))
            wall_stats = self.cursor.fetchone()

            # Count socket scans by status
            self.cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM socket_scans WHERE session_id = ?
                GROUP BY status
            """, (session_id,))
            socket_stats = dict(self.cursor.fetchall())

            summary = {
                "session_id": session[0],
                "timestamp": session[1],
                "room_id": session[2],
                "total_area": session[3],
                "wall_scans_total": wall_stats[0] if wall_stats[0] else 0,
                "wall_scans_critical": wall_stats[1] if wall_stats[1] else 0,
                "socket_stats": socket_stats,
            }

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get session summary: {e}")
            return {}

    def _add_to_sync_queue(self, table_name: str, record_id: int) -> None:
        """
        Add record to sync queue.

        Args:
            table_name: Name of table containing record.
            record_id: ID of record to sync.
        """
        try:
            self.cursor.execute("""
                INSERT INTO sync_queue (table_name, record_id, synced)
                VALUES (?, ?, 0)
            """, (table_name, record_id))

            self.connection.commit()

        except Exception as e:
            self.logger.error(f"Failed to add to sync queue: {e}")

    def cleanup(self) -> None:
        """Close database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.logger.info("Database closed")
            except Exception as e:
                self.logger.error(f"Error closing database: {e}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
