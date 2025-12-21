"""
LogSend - Python logger with Vector HTTP sink and SQLite storage.
"""

from .disk_queue import DiskQueue
from .handler import VectorHandler
from .logger import LogLevel, LogSend
from .sender import LogSender

__version__ = "0.1.0"
__all__ = ["LogSend", "LogLevel", "VectorHandler", "LogSender", "DiskQueue"]
