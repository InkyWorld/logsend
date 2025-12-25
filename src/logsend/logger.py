"""
Main logger class for LogSend.
"""

import json
import threading
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeAlias, Union

from .disk_queue import DiskQueue
from .sender import LogSender

# Maximum batch size: 50 MB
MAX_BATCH_SIZE_BYTES = 5 * 1024 * 1024

JSONValue: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    Dict[str, "JSONValue"],
    List["JSONValue"],
]

JSONObject: TypeAlias = Dict[str, JSONValue]


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
            batch_size=5000,  # Send after 5000 logs or 5 MB
            flush_interval=30.0,
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
        log_dir: Path,
        batch_size: int = 5000,
        flush_interval: float = 30.0,
        level: LogLevel = LogLevel.DEBUG,
        username: Optional[str] = None,
        password: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize LogSend logger.

        Args:
            vector_url: URL of Vector HTTP endpoint
            project: Project name (required, included in every log)
            table: Table name (required, included in every log)
            batch_size: Maximum number of logs to send per batch (default: 5000)
            flush_interval: Seconds between automatic flushes
            level: Minimum log level to process
            username: Optional username for Basic Auth
            password: Optional password for Basic Auth
            extra_fields: Extra fields to include in every log entry
        """
        if not project:
            raise ValueError("project is required")
        if not table:
            raise ValueError("table is required")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self.vector_url = vector_url
        self.project = project
        self.table = table
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.level = level
        self.extra_fields = extra_fields or {}

        # Create logger_buffer directory in project root
        logger_buffer_dir = log_dir / "logger_buffer"
        logger_buffer_dir.mkdir(parents=True, exist_ok=True)

        # SQLite queue for persistence
        self._queue = DiskQueue(str(logger_buffer_dir / "queue.db"))

        # HTTP sender
        self._sender = LogSender(
            vector_url=vector_url, username=username, password=password
        )

        # Flush timer thread
        self._stop_event = threading.Event()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True
        )
        self._flush_thread.start()

    def _create_log_entry(
        self,
        level: LogLevel | None,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a log entry dictionary."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "project": self.project,
            "table": self.table,
            **self.extra_fields,
        }
        if level is not None:
            entry["level"] = level.name

        if extra:
            entry["extra"] = extra

        return entry

    def _log(
        self,
        message: Union[str, JSONObject],
        level: Optional[LogLevel] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal logging method."""
        if level is not None and level < self.level:
            return

        if isinstance(message, str):
            entry = self._create_log_entry(level, message, extra)
        else:
            # message is a dict (JSONObject)
            entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                **message,
                "project": self.project,
                "table": self.table,
                **self.extra_fields,
            }
            if level is not None:
                entry["level"] = level.name
            if extra:
                entry["extra"] = extra

        message_json = json.dumps(entry, ensure_ascii=False)

        # Add directly to queue
        self._queue.enqueue(message_json)

    def _flush_buffer(self) -> None:
        """Flush logs from queue and try to send."""
        # Try to send from queue in background
        threading.Thread(target=self._send_from_queue, daemon=True).start()

    def _send_from_queue(self) -> None:
        """Send logs from queue to Vector."""
        while True:
            # Get a batch, but ensure it doesn't exceed 50 MB
            batch = []
            batch_size_bytes = 0

            # Peek at messages and build batch respecting size limit
            remaining = self._queue.peek_batch(self.batch_size)
            for msg in remaining:
                msg_bytes = len(msg.encode("utf-8"))
                if (
                    batch_size_bytes + msg_bytes > MAX_BATCH_SIZE_BYTES
                    and batch
                ):
                    # Batch is full, send what we have
                    break
                batch.append(msg)
                batch_size_bytes += msg_bytes

            if not batch:
                break

            # Remove from queue only after successful send
            self._queue.dequeue_batch(len(batch))
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
        self._log(message, LogLevel.DEBUG, extra)

    def info(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an info message."""
        self._log(message, LogLevel.INFO, extra)

    def warning(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a warning message."""
        self._log(message, LogLevel.WARNING, extra)

    def error(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an error message."""
        self._log(message, LogLevel.ERROR, extra)

    def critical(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a critical message."""
        self._log(message, LogLevel.CRITICAL, extra)

    def flush(self) -> None:
        """Manually flush the buffer and send logs."""
        self._flush_buffer()

    def pending_count(self) -> int:
        """Get the number of pending logs in queue."""
        return self._queue.size()

    def json(
        self, json_obj: JSONObject, level: Optional[LogLevel] = None
    ) -> None:
        """Log a JSON object."""
        self._log(json_obj, level)

    def close(self) -> None:
        """Close the logger and flush remaining logs."""
        self._stop_event.set()
        self._flush_thread.join(timeout=2.0)

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
