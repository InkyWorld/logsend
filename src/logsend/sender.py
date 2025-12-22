"""
HTTP sender for Vector.
"""

import time
from typing import Dict, List, Optional

import requests


class LogSender:
    """
    Sends logs to Vector via HTTP.

    Supports batch sending and automatic retries.
    """

    def __init__(
        self,
        vector_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize LogSender.

        Args:
            vector_url: URL of Vector HTTP endpoint
            headers: Additional headers to send with requests
        """
        self.vector_url = vector_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/x-ndjson",
                **self.headers,
            }
        )

    def send_batch(self, messages: List[str]) -> bool:
        """
        Send a batch of log messages to Vector.

        Args:
            messages: List of JSON strings to send

        Returns:
            True if send was successful, False otherwise
        """
        if not messages:
            return True

        # Vector expects newline-delimited JSON
        payload = "\n".join(messages)
        try:
            response = self._session.post(
                self.vector_url,
                data=payload.encode("utf-8"),
                timeout=self.timeout,
            )

            if response.status_code < 300:
                return True
            return False

        except requests.exceptions.RequestException:
            return False

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
