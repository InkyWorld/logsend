"""
Disk queue using SQLite for persistent log storage.
"""

import sqlite3
import threading
from typing import List, Tuple, Optional


class DiskQueue:
    """
    Simple queue backed by SQLite for persistent log storage.
    """

    def __init__(self, db_path: str):
        """
        Initialize DiskQueue.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS log_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Index for faster ordering
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_log_queue_id ON log_queue(id)
            """)

    def enqueue(self, message: str) -> None:
        """
        Add a message to the queue.
        
        Args:
            message: JSON string to enqueue
        """
        with self.lock:
            self.conn.execute(
                "INSERT INTO log_queue(message) VALUES (?)",
                (message,)
            )
            self.conn.commit()

    def enqueue_batch(self, messages: List[str]) -> None:
        """
        Add multiple messages to the queue.
        
        Args:
            messages: List of JSON strings to enqueue
        """
        if not messages:
            return
        with self.lock:
            self.conn.executemany(
                "INSERT INTO log_queue(message) VALUES (?)",
                [(m,) for m in messages]
            )
            self.conn.commit()

    def dequeue_batch(self, limit: int) -> List[str]:
        """
        Get and remove up to limit messages from the queue.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages
        """
        with self.lock:
            cur = self.conn.execute(
                "SELECT id, message FROM log_queue ORDER BY id ASC LIMIT ?",
                (limit,)
            )
            rows = cur.fetchall()
            
            if not rows:
                return []

            ids = [r[0] for r in rows]
            messages = [r[1] for r in rows]
            
            # Delete retrieved messages
            placeholders = ",".join("?" * len(ids))
            self.conn.execute(
                f"DELETE FROM log_queue WHERE id IN ({placeholders})",
                ids
            )
            self.conn.commit()
            
            return messages

    def peek_batch(self, limit: int) -> List[str]:
        """
        Get up to limit messages without removing them.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages
        """
        with self.lock:
            cur = self.conn.execute(
                "SELECT message FROM log_queue ORDER BY id ASC LIMIT ?",
                (limit,)
            )
            return [r[0] for r in cur.fetchall()]

    def requeue(self, messages: List[str]) -> None:
        """
        Put messages back to the queue (for failed sends).
        
        Args:
            messages: List of messages to requeue
        """
        self.enqueue_batch(messages)

    def size(self) -> int:
        """
        Get the number of messages in the queue.
        
        Returns:
            Queue size
        """
        with self.lock:
            cur = self.conn.execute("SELECT COUNT(*) FROM log_queue")
            return cur.fetchone()[0]

    def clear(self) -> None:
        """Clear all messages from the queue."""
        with self.lock:
            self.conn.execute("DELETE FROM log_queue")
            self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        with self.lock:
            self.conn.close()
