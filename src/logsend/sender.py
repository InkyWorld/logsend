"""
HTTP sender for Vector.
"""

from typing import Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth


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
        session: Optional[requests.Session] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize LogSender.

        Args:
            vector_url: URL of Vector HTTP endpoint
            headers: Additional headers to send with requests
            timeout: Request timeout in seconds
            session: Custom requests.Session to use (e.g., shared by application)
            username: Optional username for Basic Auth
            password: Optional password for Basic Auth
        """
        self.vector_url = vector_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.username = username
        self.password = password
        self._owns_session = session is None
        self._session = (
            self._build_session()
            if session is None
            else self._prepare_session(session)
        )

    def _build_session(self) -> requests.Session:
        return self._prepare_session(requests.Session())

    def _prepare_session(self, session: requests.Session) -> requests.Session:
        # Ensure required headers while preserving caller-provided ones
        session.headers.update(
            {
                "Content-Type": "application/x-ndjson",
                **self.headers,
            }
        )
        # Set up Basic Auth if credentials provided
        if self.username and self.password:
            session.auth = HTTPBasicAuth(self.username, self.password)
        return session

    def reset_session(
        self, new_session: Optional[requests.Session] = None
    ) -> None:
        """Replace the current HTTP session.

        Passing ``new_session`` allows callers to swap in their own session
        instance, otherwise a fresh internal session is created. Existing
        internally-owned sessions are closed before replacement.
        """
        if self._owns_session and self._session:
            self._session.close()

        if new_session is not None:
            self._session = self._prepare_session(new_session)
            self._owns_session = False
        else:
            self._session = self._build_session()
            self._owns_session = True

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

        # Vector expects newline-delimited JSON as bytes
        payload = "\n".join(messages)
        payload_bytes = payload.encode("utf-8")
        try:
            response = self._session.post(
                self.vector_url,
                data=payload_bytes,
                timeout=self.timeout,
            )

            if response.status_code < 300:
                return True
            return False

        except requests.exceptions.RequestException:
            if self._owns_session:
                # Refresh internal session so future sends can recover cleanly
                self.reset_session()
            return False

    def close(self) -> None:
        """Close the HTTP session."""
        if self._owns_session:
            self._session.close()
