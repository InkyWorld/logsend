"""
Python logger with SQLite storage for sending logs to Vector via HTTP.
"""

from .logger import LogLevel, LogSend

__version__ = "0.2.0"
__all__ = ["LogSend", "LogLevel"]
