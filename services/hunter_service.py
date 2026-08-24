"""Hunter.io Professional Email Discovery Service.

Integrates with Hunter.io API (Domain Search & Email Finder) to discover
verified professional and business contact emails for discovered companies/domains.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)

# Business email prefix priority ranking
PRIORITY_PREFIXES = [
    "sales@",
    "wholesale@",
    "orders@",
    "info@",
    "contact@",
    "business@",
]

# Domains that should not be queried against Hunter (social platforms & giant marketplaces)
SKIP_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "pinterest.com",
    "tiktok.com",
    "amazon.com",
    "ebay.com",
    "etsy.com",
    "google.com",
    "wikipedia.org",
    "yahoo.com",
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "apple.com",
    "microsoft.com",
    "walmart.com",
    "alibaba.com",
    "aliexpress.com",
}

# Obvious dummy or test addresses
IGNORE_EMAILS = {
    "example@example.com",
    "test@test.com",
    "user@example.com",
    "email@example.com",
    "email@domain.com",
    "name@domain.com",
    "yourname@email.com",
    "info@yourdomain.com",
    "support@example.com",
    "admin@example.com",
}


class HunterService:
    """Service to discover verified business emails using Hunter.io API."""

    def __init__(self, api_key: str = "", base_url: str = "https://api.hunter.io/v2"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.hunter.io/v2").rstrip("/")
        self.session = requests.Session()

    @staticmethod
    def extract_clean_domain(url_or_domain: str) -> str:
        """Extract the root domain from a full URL or hostname."""
        if not url_or_domain or not isinstance(url_or_domain, str):
            return ""
        cleaned = url_or_domain.strip()
        if not cleaned.startswith(("http://", "https://")):
            cleaned = "https://" + cleaned
        try:
            parsed = urlparse(cleaned)
            netloc = (parsed.netloc or "").lower().split(":")[0]  # remove port if present
            # Remove leading www. and subdomains if common
            netloc = re.sub(r"^www\d*\.", "", netloc)
            return netloc.strip()
        except Exception:
            return ""

    @staticmethod
    def validate_email_syntax(email: str) -> bool:
        """Basic email format and anti-placeholder check."""
        if not email or not isinstance(email, str):
            return False
        cleaned = email.strip().lower()
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"
        if not bool(re.match(pattern, cleaned)):
            return False
        if cleaned in IGNORE_EMAILS:
            return False
        if cleaned.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".css", ".js")):
            return False
        return True

    @staticmethod
    def select_best_hunter_email(emails_data: List[Dict[str, Any]]) -> str:
        """Select the most appropriate business/commercial email from Hunter's candidate list."""
        if not emails_data:
            return ""

        valid_candidates: List[Dict[str, Any]] = []
        for item in emails_data:
            val = (item.get("value") or "").strip().lower()
            if HunterService.validate_email_syntax(val):
                valid_candidates.append({
                    "email": val,
                    "type": item.get("type", "generic"),
                    "confidence": item.get("confidence", 0) or 0,
                    "department": (item.get("department") or "").lower(),
                    "position": (item.get("position") or "").lower(),
                })

        if not valid_candidates:
            return ""

        # 1. Check priority prefixes (sales, wholesale, orders, info, contact, business)
        for prefix in PRIORITY_PREFIXES:
            for cand in valid_candidates:
                if cand["email"].startswith(prefix):
                    return cand["email"]

        # 2. Check department or position relevant to trade/sales/management
        for cand in valid_candidates:
            dept = cand["department"]
            pos = cand["position"]
            if any(kw in dept or kw in pos for kw in ["sales", "wholesale", "commercial", "trade", "owner", "founder", "manager"]):
                return cand["email"]

        # 3. Prefer generic company addresses over personal addresses if available
        generics = [c for c in valid_candidates if c["type"] == "generic"]
        if generics:
            # Sort by confidence
            generics.sort(key=lambda x: x["confidence"], reverse=True)
            return generics[0]["email"]

        # 4. Fallback to highest confidence candidate
        valid_candidates.sort(key=lambda x: x["confidence"], reverse=True)
        return valid_candidates[0]["email"]

    def find_email(self, domain: str, company_name: Optional[str] = None) -> str:
        """Find professional contact email for a domain using Hunter.io Domain Search API.

        Args:
            domain: Target domain or URL.
            company_name: Optional company name for context.

        Returns:
            Discovered email string, or empty string if not found / error.
        """
        if not self.api_key:
            logger.debug("HUNTER_API_KEY is not configured; skipping Hunter email search.")
            return ""

        clean_domain = self.extract_clean_domain(domain)
        if not clean_domain:
            return ""

        # Avoid wasting API credits on social platforms / marketplaces
        if clean_domain in SKIP_DOMAINS or any(clean_domain.endswith(f".{sd}") for sd in SKIP_DOMAINS):
            logger.debug(f"Skipping platform domain from Hunter search: {clean_domain}")
            return ""

        endpoint = f"{self.base_url}/domain-search"
        params = {
            "domain": clean_domain,
            "api_key": self.api_key,
            "limit": 10,
        }

        try:
            resp = self.session.get(endpoint, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                emails_list = data.get("emails", [])
                if emails_list:
                    best = self.select_best_hunter_email(emails_list)
                    if best:
                        logger.info(f"Hunter.io discovered email for {clean_domain}: {best}")
                        return best

            elif resp.status_code == 404:
                logger.debug(f"Hunter.io found no records for domain: {clean_domain}")
                return ""
            elif resp.status_code in (401, 403):
                logger.warning(f"Hunter.io authentication failure ({resp.status_code}). Check HUNTER_API_KEY.")
                return ""
            elif resp.status_code == 429:
                logger.warning("Hunter.io rate limit reached.")
                return ""
            else:
                logger.debug(f"Hunter.io request returned status {resp.status_code} for {clean_domain}")
                return ""

        except (requests.exceptions.RequestException, Exception) as err:
            logger.warning(f"Hunter.io API request error for {clean_domain}: {err}")
            return ""

        return ""

    def find_emails_for_leads(
        self,
        leads: List[Dict[str, Any]],
        stats_tracker: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """Enrich a batch of leads using Hunter.io for leads without valid emails."""
        if stats_tracker is None:
            stats_tracker = {"hunter_checked": 0, "hunter_emails_found": 0}

        for lead in leads:
            existing_email = (lead.get("email") or "").strip().lower()
            if existing_email and self.validate_email_syntax(existing_email):
                # Do NOT overwrite existing valid email
                continue

            website = lead.get("website") or ""
            domain = self.extract_clean_domain(website)
            if domain:
                if "hunter_checked" in stats_tracker:
                    stats_tracker["hunter_checked"] += 1

                discovered = self.find_email(domain, company_name=lead.get("company_name"))
                if discovered:
                    lead["email"] = discovered
                    if "hunter_emails_found" in stats_tracker:
                        stats_tracker["hunter_emails_found"] += 1

        return leads
