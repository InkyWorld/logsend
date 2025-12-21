"""
LogSend - Python logger with Vector HTTP sink and SQLite storage.
"""

from .logger import LogSend, LogLevel
from .handler import VectorHandler
from .sender import LogSender
from .disk_queue import DiskQueue

__version__ = "0.1.0"
__all__ = ["LogSend", "LogLevel", "VectorHandler", "LogSender", "DiskQueue"]
