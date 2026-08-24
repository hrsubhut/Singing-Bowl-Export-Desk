"""Alibaba Global Trade Discovery Source Adapter.

Supplementary discovery adapter for international buyers and sourcing companies on Alibaba.
Strictly respects access controls and official API protocols without aggressive scraping.
"""

import logging
from typing import Dict, Any
from services.lead_sources.base_source import BaseLeadSource

logger = logging.getLogger(__name__)


class AlibabaLeadSource(BaseLeadSource):
    """Alibaba Global Trade discovery source adapter."""

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(source_name="alibaba", source_platform="Alibaba")
        self.api_key = api_key
        self.api_url = api_url

    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute Alibaba buyer discovery via official Open Platform API if configured."""
        if not self.api_key and not self.api_url:
            logger.info("Alibaba lead source: No permitted API/public interface configured. Marking unavailable.")
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
            "reason": "Alibaba Open Platform App Key & Secret required"
        }
