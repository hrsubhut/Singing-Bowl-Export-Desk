"""Kompass Global B2B Directory Discovery Source Adapter.

Discovers global B2B buyers, retailers, wellness and meditation supply companies
across verified Kompass business directories.
"""

import logging
from typing import Dict, Any
from services.lead_sources.base_source import BaseLeadSource

logger = logging.getLogger(__name__)


class KompassLeadSource(BaseLeadSource):
    """Kompass B2B Directory discovery source adapter."""

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(source_name="kompass", source_platform="Kompass")
        self.api_key = api_key
        self.api_url = api_url

    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute Kompass B2B buyer discovery."""
        if not self.api_key and not self.api_url:
            logger.info("Kompass lead source: No permitted API/public interface configured. Marking unavailable.")
            return {
                "status": "unavailable",
                "found": 0,
                "leads": [],
                "reason": "No permitted API/public interface configured"
            }

        return {
            "status": "unavailable",
            "found": 0,
            "leads": [],
            "reason": "Kompass API enterprise key required"
        }
