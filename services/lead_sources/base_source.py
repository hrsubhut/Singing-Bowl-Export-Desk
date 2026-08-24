"""Base Lead Source Interface.

Defines the common contract and normalization schema for all B2B buyer discovery sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class BaseLeadSource(ABC):
    """Abstract base class for all buyer discovery source adapters."""

    def __init__(self, source_name: str, source_platform: str):
        self.source_name = source_name
        self.source_platform = source_platform

    @abstractmethod
    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute buyer discovery query on this lead source.

        Args:
            query: Base product search keywords.
            country: Country code or region (e.g., 'US', 'DE').
            limit: Maximum records to return.

        Returns:
            Dict containing:
                - status: 'success' | 'unavailable' | 'error'
                - found: int (number of leads discovered)
                - leads: List[Dict[str, Any]] (normalized buyer records)
                - reason: Optional[str] (reason if unavailable or error)
        """
        pass

    def create_normalized_lead(
        self,
        buyer_name: str = "",
        company_name: str = "",
        email: str = "",
        website: str = "",
        country: str = "",
        source_platform: Optional[str] = None,
        classification: str = "PENDING",
        status: str = "NEW",
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a single standardized buyer record conforming strictly to buyers.csv schema."""
        now_utc = created_at or datetime.now(timezone.utc).isoformat()
        platform = source_platform or self.source_platform

        c_name = (company_name or "").strip()
        b_name = (buyer_name or "").strip() or c_name or "Singing Bowl Buyer"

        return {
            "buyer_name": b_name,
            "company_name": c_name or b_name,
            "email": (email or "").strip().lower(),
            "website": (website or "").strip(),
            "country": (country or "").strip().upper(),
            "source_platform": platform,
            "classification": classification or "PENDING",
            "status": status or "NEW",
            "created_at": now_utc,
        }
