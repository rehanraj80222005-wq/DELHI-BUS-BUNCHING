import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

from src.config import settings
from src.ingestion.protobuf_parser import ProtobufParser

logger = logging.getLogger(__name__)


class OTDRealtimeClient:
    """Client for querying the Delhi Open Transit Data real-time GTFS feed."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or settings.api_key
        self.base_url = base_url or settings.gtfs.realtime_url
        self.timeout = timeout or settings.gtfs.request_timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "DBBP-TransitAnalytics/1.0",
                "Accept": "application/x-protobuf, application/octet-stream, */*",
            }
        )

    def fetch_raw(self) -> bytes:
        if not self.api_key:
            raise ValueError(
                "OTD API key is missing. Please set OTD_API_KEY in your .env file."
            )

        sanitized_url = f"{self.base_url}?key=***"
        logger.info("Requesting realtime feed from %s", sanitized_url)

        start_time = time.perf_counter()
        try:
            response = self.session.get(
                self.base_url,
                params={"key": self.api_key},
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Connection timed out querying OTD API after %s s", self.timeout)
            raise TimeoutError(f"OTD realtime API request timed out ({self.timeout}s).") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Failed to connect to OTD API server: %s", exc)
            raise ConnectionError(f"Failed to connect to OTD API server: {exc}") from exc

        duration = time.perf_counter() - start_time
        logger.info("Received HTTP %d in %.2fs (%d bytes)", response.status_code, duration, len(response.content))

        if response.status_code == 401 or response.status_code == 403:
            raise PermissionError(
                f"Authentication failed (HTTP {response.status_code}). "
                "The OTD_API_KEY in your .env is invalid or unauthorized."
            )
        if response.status_code == 404:
            raise FileNotFoundError(
                f"Endpoint not found (HTTP 404) at {sanitized_url}."
            )
        if response.status_code >= 500:
            raise RuntimeError(
                f"OTD API server error (HTTP {response.status_code}). Server may be undergoing maintenance."
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"Unexpected HTTP status {response.status_code} from OTD API: {response.text[:200]}"
            )

        return response.content

    def fetch_feed(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]:
        raw_bytes = self.fetch_raw()
        header, records = ProtobufParser.parse_feed_message(raw_bytes)
        df = ProtobufParser.to_dataframe(records)
        return header, records, df
