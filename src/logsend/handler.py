"""
Standard logging handler for integration with Python's logging module.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from .sender import LogSender
from .disk_queue import DiskQueue


class VectorHandler(logging.Handler):
    """
    Python logging handler that sends logs to Vector via HTTP.
    Uses SQLite for persistent queue storage.
    
    Can be used with Python's standard logging module for easy integration
    with existing applications.
    
    Example:
        import logging
        from logsend import VectorHandler
        
        handler = VectorHandler(
            vector_url="http://localhost:8080",
            project="my-project",
            table="app_logs",
            batch_size=50,
            flush_interval=10.0,
        )
        
        logger = logging.getLogger("my_app")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        logger.info("Hello from standard logging!")
        
        # Don't forget to close on shutdown
        handler.close()
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
        extra_fields: Optional[Dict[str, Any]] = None,
        level: int = logging.NOTSET,
    ):
        """
        Initialize VectorHandler.
        
        Args:
            vector_url: URL of Vector HTTP endpoint
            project: Project name (required, included in every log)
            table: Table name (required, included in every log)
            db_path: Path to SQLite database file for queue storage
            batch_size: Number of logs to buffer before sending
            flush_interval: Seconds between automatic flushes
            max_retries: Maximum retry attempts for failed sends
            retry_delay: Delay between retries in seconds
            extra_fields: Extra fields to include in every log entry
            level: Minimum log level to process
        """
        super().__init__(level)
        
        if not project:
            raise ValueError("project is required")
        if not table:
            raise ValueError("table is required")
        
        self.vector_url = vector_url
        self.project = project
        self.table = table
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.extra_fields = extra_fields or {}
        
        # Create directory for database
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite queue
        self._queue = DiskQueue(db_path)
        
        # In-memory buffer
        self._buffer: List[str] = []
        self._buffer_lock = threading.Lock()
        
        # Sender
        self._sender = LogSender(
            vector_url=vector_url,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        
        # Flush timer thread
        self._stop_event = threading.Event()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
    
    def _format_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Convert LogRecord to dictionary."""
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "level_num": record.levelno,
            "message": self.format(record),
            "project": self.project,
            "table": self.table,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            **self.extra_fields,
        }
        
        # Include exception info if present
        if record.exc_info:
            entry["exception"] = self.formatter.formatException(record.exc_info) if self.formatter else str(record.exc_info)
        
        # Include extra attributes
        extra_attrs = {}
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "asctime", "taskName",
            ):
                try:
                    json.dumps(value)  # Check if serializable
                    extra_attrs[key] = value
                except (TypeError, ValueError):
                    extra_attrs[key] = str(value)
        
        if extra_attrs:
            entry["extra"] = extra_attrs
        
        return entry
    
    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record."""
        try:
            entry = self._format_record(record)
            message_json = json.dumps(entry, ensure_ascii=False)
            
            with self._buffer_lock:
                self._buffer.append(message_json)
                
                if len(self._buffer) >= self.batch_size:
                    self._flush_buffer()
                    
        except Exception:
            self.handleError(record)
    
    def _flush_buffer(self) -> None:
        """Flush the buffer to queue and try to send."""
        with self._buffer_lock:
            if not self._buffer:
                return
            
            self._queue.enqueue_batch(self._buffer)
            self._buffer.clear()
        
        threading.Thread(target=self._send_from_queue, daemon=True).start()
    
    def _send_from_queue(self) -> None:
        """Send logs from queue to Vector."""
        while True:
            batch = self._queue.dequeue_batch(self.batch_size)
            if not batch:
                break
            
            success = self._sender.send_batch(batch)
            if not success:
                self._queue.requeue(batch)
                break
    
    def _flush_loop(self) -> None:
        """Background thread that periodically flushes the buffer."""
        while not self._stop_event.is_set():
            self._stop_event.wait(self.flush_interval)
            if not self._stop_event.is_set():
                self._flush_buffer()
    
    def flush(self) -> None:
        """Manually flush the buffer."""
        self._flush_buffer()
    
    def close(self) -> None:
        """Close the handler."""
        self._stop_event.set()
        self._flush_thread.join(timeout=2.0)
        
        # Final flush
        with self._buffer_lock:
            if self._buffer:
                self._queue.enqueue_batch(self._buffer)
                self._buffer.clear()
        
        # Try to send remaining
        self._send_from_queue()
        
        # Close resources
        self._queue.close()
        self._sender.close()
        super().close()
