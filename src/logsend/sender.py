"""
HTTP sender for Vector.
"""

import time
from typing import List, Dict, Any, Optional

import requests


class LogSender:
    """
    Sends logs to Vector via HTTP.
    
    Supports batch sending and automatic retries.
    """
    
    def __init__(
        self,
        vector_url: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize LogSender.
        
        Args:
            vector_url: URL of Vector HTTP endpoint
            max_retries: Maximum retry attempts for failed sends
            retry_delay: Delay between retries in seconds
            timeout: Request timeout in seconds
            headers: Additional headers to send with requests
        """
        self.vector_url = vector_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.headers = headers or {}
        
        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/x-ndjson",
            **self.headers,
        })
    
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
        
        for attempt in range(self.max_retries):
            try:
                response = self._session.post(
                    self.vector_url,
                    data=payload.encode("utf-8"),
                    timeout=self.timeout,
                )
                
                if response.status_code < 300:
                    return True
                
                # Retry on server errors
                if response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                
                return False
                
            except requests.exceptions.RequestException:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                return False
        
        return False
    
    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
