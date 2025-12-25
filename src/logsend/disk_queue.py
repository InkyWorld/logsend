"""
Disk queue using SQLite for persistent log storage.
"""

import sqlite3
import threading
from typing import Callable, List, Optional, TypeVar

T = TypeVar("T")


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
        self.lock = threading.Lock()
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self) -> None:
        """Establish a SQLite connection and ensure schema is ready."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _ensure_connection(self) -> None:
        """Ensure there is an active SQLite connection."""
        if self.conn is None:
            self._connect()

    def _reconnect(self) -> None:
        """Drop the current connection and open a new one."""
        if self.conn is not None:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass
        self.conn = None
        self._connect()

    def _run_with_retry(self, operation: Callable[[], T]) -> T:
        """Run a DB operation, reopening the connection once if needed."""
        last_exc: Optional[sqlite3.Error] = None
        for _ in range(2):
            self._ensure_connection()
            try:
                return operation()
            except sqlite3.Error as exc:
                last_exc = exc
                self._reconnect()
        assert last_exc is not None
        raise last_exc

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self.conn
        if conn is None:
            raise RuntimeError("Database connection unavailable")
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Index for faster ordering
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_log_queue_id ON log_queue(id)
            """)

    def enqueue(self, message: str) -> None:
        """
        Add a message to the queue.

        Args:
            message: JSON string to enqueue
        """

        def operation() -> None:
            conn = self.conn
            if conn is None:
                raise RuntimeError("Database connection unavailable")
            conn.execute(
                "INSERT INTO log_queue(message) VALUES (?)", (message,)
            )
            conn.commit()

        with self.lock:
            self._run_with_retry(operation)

    def enqueue_batch(self, messages: List[str]) -> None:
        """
        Add multiple messages to the queue.

        Args:
            messages: List of JSON strings to enqueue
        """
        if not messages:
            return

        def operation() -> None:
            conn = self.conn
            if conn is None:
                raise RuntimeError("Database connection unavailable")
            conn.executemany(
                "INSERT INTO log_queue(message) VALUES (?)",
                [(m,) for m in messages],
            )
            conn.commit()

        with self.lock:
            self._run_with_retry(operation)

    def dequeue_batch(self, limit: int) -> List[str]:
        """
        Get and remove up to limit messages from the queue.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages
        """

        def operation() -> List[str]:
            conn = self.conn
            if conn is None:
                raise RuntimeError("Database connection unavailable")
            cur = conn.execute(
                "SELECT id, message FROM log_queue ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()

            if not rows:
                return []

            ids = [r[0] for r in rows]
            messages = [r[1] for r in rows]

            # Delete retrieved messages
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"DELETE FROM log_queue WHERE id IN ({placeholders})", ids
            )
            conn.commit()

            return messages

        with self.lock:
            return self._run_with_retry(operation)

    def peek_batch(self, limit: int) -> List[str]:
        """
        Get up to limit messages without removing them.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages
        """

        def operation() -> List[str]:
            conn = self.conn
            if conn is None:
                raise RuntimeError("Database connection unavailable")
            cur = conn.execute(
                "SELECT message FROM log_queue ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            return [r[0] for r in cur.fetchall()]

        with self.lock:
            return self._run_with_retry(operation)

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

        def operation() -> int:
            conn = self.conn
            if conn is None:
                raise RuntimeError("Database connection unavailable")
            cur = conn.execute("SELECT COUNT(*) FROM log_queue")
            return cur.fetchone()[0]

        with self.lock:
            return self._run_with_retry(operation)

    def clear(self) -> None:
        """Clear all messages from the queue."""

        def operation() -> None:
            conn = self.conn
            if conn is None:
                raise RuntimeError("Database connection unavailable")
            conn.execute("DELETE FROM log_queue")
            conn.commit()

        with self.lock:
            self._run_with_retry(operation)

    def close(self) -> None:
        """Close the database connection."""
        with self.lock:
            if self.conn is not None:
                self.conn.close()
                self.conn = None
