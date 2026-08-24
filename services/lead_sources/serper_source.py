"""Google / Serper Lead Discovery Source Adapter.

Integrates with Serper Google Search API to discover B2B singing bowl buyers,
importers, and distributors.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests
from services.lead_sources.base_source import BaseLeadSource

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "US": "USA",
    "DE": "Germany",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "FR": "France",
    "AU": "Australia",
    "JP": "Japan",
    "CA": "Canada",
    "NL": "Netherlands",
    "IT": "Italy",
    "ES": "Spain",
    "AT": "Austria",
    "CH": "Switzerland",
    "IN": "India",
}


class SerperLeadSource(BaseLeadSource):
    """Google Search Lead Source via Serper API."""

    def __init__(self, api_key: str = "", api_url: str = "https://google.serper.dev/search"):
        super().__init__(source_name="serper", source_platform="Google/Serper")
        self.api_key = api_key
        self.api_url = api_url or "https://google.serper.dev/search"

    @staticmethod
    def extract_company_name(title: str, link: str) -> str:
        """Extract a readable business / company name from the title or domain."""
        try:
            netloc = urlparse(link).netloc.replace("www.", "")
            domain_name = netloc.split(".")[0].replace("-", " ").title()
        except Exception:
            domain_name = "Singing Bowl Buyer"

        if not title:
            return domain_name

        for sep in ["|", "–", "—", "-", ":"]:
            if sep in title:
                parts = [p.strip() for p in title.split(sep) if p.strip()]
                if parts:
                    return parts[0]

        return title[:60].strip()

    def search(self, query: str, country: str = "", limit: int = 10) -> Dict[str, Any]:
        """Execute Google Search query via Serper API."""
        if not self.api_key:
            return {
                "status": "unavailable",
                "found": 0,
                "leads": [],
                "reason": "LEAD_SEARCH_API_KEY is not configured in environment."
            }

        clean_query = query.strip()
        country_code = country.strip().upper() if country else ""
        country_display = COUNTRY_NAMES.get(country_code, country_code)

        if country_display and country_display.lower() not in clean_query.lower():
            augmented_query = f"{clean_query} {country_display}"
        else:
            augmented_query = clean_query

        num_results = min(max(int(limit), 1), 100)
        payload: Dict[str, Any] = {
            "q": augmented_query,
            "num": num_results,
        }

        if country_code and len(country_code) == 2:
            payload["gl"] = country_code.lower()

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()

            data = response.json()
            organic_results = data.get("organic", [])

            extracted_leads: List[Dict[str, Any]] = []
            now_utc = datetime.now(timezone.utc).isoformat()

            for item in organic_results:
                title = (item.get("title") or "").strip()
                link = (item.get("link") or "").strip()
                snippet = (item.get("snippet") or "").strip()

                if not link:
                    continue

                company_name = self.extract_company_name(title, link)
                buyer_name = title if title else company_name

                lead = self.create_normalized_lead(
                    buyer_name=buyer_name,
                    company_name=company_name,
                    email="",
                    website=link,
                    country=country_code or country,
                    source_platform=self.source_platform,
                    classification="PENDING",
                    status="NEW",
                    created_at=now_utc,
                )
                extracted_leads.append(lead)

            return {
                "status": "success",
                "found": len(extracted_leads),
                "leads": extracted_leads,
                "reason": None
            }

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 502
            logger.warning(f"Serper API HTTP Error ({status_code}): {e}")
            return {
                "status": "error",
                "found": 0,
                "leads": [],
                "reason": f"Serper API HTTP Error ({status_code}): {e.response.text if e.response is not None else str(e)}"
            }
        except requests.exceptions.RequestException as e:
            logger.warning(f"Serper API connection error: {e}")
            return {
                "status": "error",
                "found": 0,
                "leads": [],
                "reason": f"Serper API network connection failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in Serper source: {e}", exc_info=True)
            return {
                "status": "error",
                "found": 0,
                "leads": [],
                "reason": f"Unexpected error: {str(e)}"
            }
