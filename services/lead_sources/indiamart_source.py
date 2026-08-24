"""IndiaMART B2B Marketplace Discovery Source Adapter.

Discovers B2B importers, wholesalers, distributors, and buyers on IndiaMART.
"""

import logging
from typing import Dict, Any
from services.lead_sources.base_source import BaseLeadSource

logger = logging.getLogger(__name__)


class IndiaMARTLeadSource(BaseLeadSource):
    """IndiaMART B2B discovery source adapter."""

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(source_name="indiamart", source_platform="IndiaMART")
        self.api_key = api_key
        self.api_url = api_url

    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute IndiaMART B2B buyer discovery."""
        if not self.api_key and not self.api_url:
            logger.info("IndiaMART lead source: No permitted API/public interface configured. Marking unavailable.")
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
            "reason": "IndiaMART CRM Lead API key required"
        }
