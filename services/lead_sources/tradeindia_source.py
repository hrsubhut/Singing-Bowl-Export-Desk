"""TradeIndia B2B Portal Discovery Source Adapter.

Discovers B2B buyers, wholesalers, and importers on TradeIndia.
"""

import logging
from typing import Dict, Any
from services.lead_sources.base_source import BaseLeadSource

logger = logging.getLogger(__name__)


class TradeIndiaLeadSource(BaseLeadSource):
    """TradeIndia B2B discovery source adapter."""

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(source_name="tradeindia", source_platform="TradeIndia")
        self.api_key = api_key
        self.api_url = api_url

    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute TradeIndia B2B buyer discovery."""
        if not self.api_key and not self.api_url:
            logger.info("TradeIndia lead source: No permitted API/public interface configured. Marking unavailable.")
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
            "reason": "TradeIndia API User ID & Key required"
        }
