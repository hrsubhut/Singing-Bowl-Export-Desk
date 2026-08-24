"""Global Sources International Buyer Discovery Source Adapter.

Discovers international buyers, importers, distributors, and sourcing companies
on Global Sources trade directory.
"""

import logging
from typing import Dict, Any
from services.lead_sources.base_source import BaseLeadSource

logger = logging.getLogger(__name__)


class GlobalSourcesLeadSource(BaseLeadSource):
    """Global Sources trade directory discovery source adapter."""

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(source_name="globalsources", source_platform="Global Sources")
        self.api_key = api_key
        self.api_url = api_url

    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute Global Sources buyer discovery."""
        if not self.api_key and not self.api_url:
            logger.info("Global Sources lead source: No permitted API/public interface configured. Marking unavailable.")
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
            "reason": "Global Sources API partner authorization required"
        }
