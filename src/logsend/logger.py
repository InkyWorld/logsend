"""
Main logger class for LogSend.
"""

import json
import threading
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .disk_queue import DiskQueue
from .sender import LogSender


class LogLevel(IntEnum):
    """Log levels."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogSend:
    """
    Logger that sends logs to Vector via HTTP and stores them in SQLite.

    Features:
    - Buffered sending (by count or timer)
    - Background sending thread
    - SQLite storage for persistence
    - Automatic retry on failure

    Example:
        logger = LogSend(
            vector_url="http://localhost:8080",
            project="my-project",
            table="app_logs",
            db_path="./logs/queue.db",
            batch_size=100,
            flush_interval=5.0,
        )

        logger.info("Application started")
        logger.error("Something went wrong", extra={"user_id": 123})

        # Don't forget to close on shutdown
        logger.close()
    """

    def __init__(
        self,
        vector_url: str,
        project: str,
        table: str,
        db_path: str = "./logs/queue.db",
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        level: LogLevel = LogLevel.DEBUG,
        extra_fields: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize LogSend logger.

        Args:
            vector_url: URL of Vector HTTP endpoint
            project: Project name (required, included in every log)
            table: Table name (required, included in every log)
            db_path: Path to SQLite database file for queue storage
            batch_size: Number of logs to buffer before sending
            flush_interval: Seconds between automatic flushes
            max_retries: Maximum retry attempts for failed sends
            retry_delay: Delay between retries in seconds
            level: Minimum log level to process
            extra_fields: Extra fields to include in every log entry
        """
        if not project:
            raise ValueError("project is required")
        if not table:
            raise ValueError("table is required")

        self.vector_url = vector_url
        self.project = project
        self.table = table
        self.db_path = db_path
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.level = level
        self.extra_fields = extra_fields or {}

        # Create directory for database
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # SQLite queue for persistence
        self._queue = DiskQueue(db_path)

        # In-memory buffer for batching
        self._buffer: List[str] = []
        self._buffer_lock = threading.Lock()

        # HTTP sender
        self._sender = LogSender(
            vector_url=vector_url,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        # Flush timer thread
        self._stop_event = threading.Event()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True
        )
        self._flush_thread.start()

    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a log entry dictionary."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.name,
            "level_num": int(level),
            "message": message,
            "project": self.project,
            "table": self.table,
            **self.extra_fields,
        }

        if extra:
            entry["extra"] = extra

        return entry

    def _log(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal logging method."""
        if level < self.level:
            return

        entry = self._create_log_entry(level, message, extra)
        message_json = json.dumps(entry, ensure_ascii=False)

        # Add to buffer
        with self._buffer_lock:
            self._buffer.append(message_json)

            # Flush if buffer is full
            if len(self._buffer) >= self.batch_size:
                self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Flush the in-memory buffer to queue and try to send."""
        with self._buffer_lock:
            if not self._buffer:
                return

            # Move buffer to queue
            self._queue.enqueue_batch(self._buffer)
            self._buffer.clear()

        # Try to send from queue in background
        threading.Thread(target=self._send_from_queue, daemon=True).start()

    def _send_from_queue(self) -> None:
        """Send logs from queue to Vector."""
        while True:
            batch = self._queue.dequeue_batch(self.batch_size)
            if not batch:
                break

            success = self._sender.send_batch(batch)
            if not success:
                # Put back failed messages
                self._queue.requeue(batch)
                break

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes the buffer."""
        while not self._stop_event.is_set():
            self._stop_event.wait(self.flush_interval)
            if not self._stop_event.is_set():
                self._flush_buffer()

    def debug(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a debug message."""
        self._log(LogLevel.DEBUG, message, extra)

    def info(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an info message."""
        self._log(LogLevel.INFO, message, extra)

    def warning(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a warning message."""
        self._log(LogLevel.WARNING, message, extra)

    def error(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an error message."""
        self._log(LogLevel.ERROR, message, extra)

    def critical(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a critical message."""
        self._log(LogLevel.CRITICAL, message, extra)

    def log(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a message with specified level."""
        self._log(level, message, extra)

    def flush(self) -> None:
        """Manually flush the buffer and send logs."""
        self._flush_buffer()

    def pending_count(self) -> int:
        """Get the number of pending logs in queue."""
        with self._buffer_lock:
            return len(self._buffer) + self._queue.size()

    def close(self) -> None:
        """Close the logger and flush remaining logs."""
        self._stop_event.set()
        self._flush_thread.join(timeout=2.0)

        # Final flush
        with self._buffer_lock:
            if self._buffer:
                self._queue.enqueue_batch(self._buffer)
                self._buffer.clear()

        # Try to send remaining logs
        self._send_from_queue()

        # Close resources
        self._queue.close()
        self._sender.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
