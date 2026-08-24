"""Search and Lead Extraction Service with Multi-Source Buyer Discovery.

Orchestrates multi-source B2B buyer discovery across Serper, TradeKey, Europages,
Kompass, IndiaMART, TradeIndia, Alibaba, and Global Sources, with cross-source deduplication
and website email enrichment.
"""

import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin
import requests

from services.lead_sources import (
    ALL_LEAD_SOURCES,
    BaseLeadSource,
    SerperLeadSource,
    TradeKeyLeadSource,
    EuropagesLeadSource,
    KompassLeadSource,
    IndiaMARTLeadSource,
    TradeIndiaLeadSource,
    AlibabaLeadSource,
    GlobalSourcesLeadSource,
)
from services.hunter_service import HunterService

logger = logging.getLogger(__name__)

# Controlled query expansion terms for Singing Bowl export intelligence
QUERY_EXPANSIONS = [
    "importer",
    "wholesaler",
    "distributor",
    "buyer",
    "wholesale",
    "sound healing products importer",
    "meditation products distributor",
    "yoga accessories wholesaler",
]

COUNTRY_CODES = {
    "US": "USA",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "NL": "Netherlands",
    "IT": "Italy",
    "ES": "Spain",
    "AT": "Austria",
    "CH": "Switzerland",
    "CA": "Canada",
    "AU": "Australia",
    "IN": "India",
    "JP": "Japan",
}

CONTACT_SUBPATHS = [
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/wholesale",
    "/pages/contact",
]

PRIORITY_PREFIXES = [
    "sales@",
    "wholesale@",
    "orders@",
    "info@",
    "contact@",
    "business@",
]

IGNORE_EMAIL_PATTERNS = {
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
    "john.doe@example.com",
    "sentry@sentry.io",
    "wix@wix.com",
}

IGNORE_DOMAIN_SUFFIXES = (
    "example.com",
    "domain.com",
    "test.com",
    "sample.com",
    "sentry.io",
    "wixpress.com",
    "wix.com",
    "shopify.com",
    "wordpress.org",
    "gravatar.com",
    "schema.org",
    "google.com",
    "amazon.com",
    "ebay.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "cloudflare.com",
)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class SearchService:
    """Multi-source lead discovery, normalization, cross-source deduplication, and email enrichment."""

    DEFAULT_SOURCES = [
        "serper",
        "tradekey",
        "europages",
        "kompass",
        "indiamart",
        "tradeindia",
        "alibaba",
        "globalsources",
    ]

    def __init__(
        self,
        api_key: str = "",
        api_url: str = "https://google.serper.dev/search",
        hunter_service: Optional[HunterService] = None,
    ):
        self.api_key = api_key
        self.api_url = api_url or "https://google.serper.dev/search"
        self.hunter_service = hunter_service
        self.session = requests.Session()
        self.session.headers.update(HTTP_HEADERS)

        # Initialize source adapters
        self.sources: Dict[str, BaseLeadSource] = {
            "serper": SerperLeadSource(api_key=self.api_key, api_url=self.api_url),
            "tradekey": TradeKeyLeadSource(),
            "europages": EuropagesLeadSource(),
            "kompass": KompassLeadSource(),
            "indiamart": IndiaMARTLeadSource(),
            "tradeindia": TradeIndiaLeadSource(),
            "alibaba": AlibabaLeadSource(),
            "globalsources": GlobalSourcesLeadSource(),
        }

    def register_source(self, name: str, source: BaseLeadSource):
        """Register or override a lead source adapter."""
        self.sources[name.lower()] = source

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format and filter out dummy/invalid addresses."""
        if not email or not isinstance(email, str):
            return False
        cleaned = email.strip().lower()
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"
        if not bool(re.match(pattern, cleaned)):
            return False
        if cleaned in IGNORE_EMAIL_PATTERNS:
            return False
        if cleaned.endswith((
            ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
            ".css", ".js", ".woff", ".woff2", ".ttf", ".mp4",
            ".webm", ".ico"
        )):
            return False
        domain = cleaned.split("@")[-1]
        if any(domain == ig or domain.endswith(f".{ig}") for ig in IGNORE_DOMAIN_SUFFIXES):
            return False
        return True

    @staticmethod
    def select_best_email(emails: List[str]) -> str:
        """Select the most relevant business email from candidate list according to priority."""
        if not emails:
            return ""
        valid_emails: List[str] = []
        seen = set()
        for e in emails:
            cleaned = e.strip().lower().rstrip(".,:;)>\"'")
            if cleaned and cleaned not in seen and SearchService.validate_email(cleaned):
                seen.add(cleaned)
                valid_emails.append(cleaned)

        if not valid_emails:
            return ""

        for prefix in PRIORITY_PREFIXES:
            for email in valid_emails:
                if email.startswith(prefix):
                    return email

        return valid_emails[0]

    @staticmethod
    def extract_emails_from_html(html_text: str) -> List[str]:
        """Extract candidate emails from page HTML including mailto: links and visible text."""
        if not html_text or not isinstance(html_text, str):
            return []
        candidates: List[str] = []
        mailto_matches = re.findall(
            r'mailto:\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
            html_text,
            re.IGNORECASE
        )
        candidates.extend(mailto_matches)
        text_matches = re.findall(
            r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
            html_text
        )
        candidates.extend(text_matches)

        unique_valid = []
        seen = set()
        for cand in candidates:
            cleaned = cand.strip().lower().rstrip(".,:;)>\"'")
            if cleaned and cleaned not in seen and SearchService.validate_email(cleaned):
                seen.add(cleaned)
                unique_valid.append(cleaned)
        return unique_valid

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for consistent deduplication comparisons."""
        if not url:
            return ""
        try:
            parsed = urlparse(url.strip())
            netloc = parsed.netloc.lower().replace("www.", "")
            path = parsed.path.rstrip("/")
            return f"{netloc}{path}"
        except Exception:
            return url.strip().lower()

    @staticmethod
    def extract_clean_domain(url: str) -> str:
        """Extract root domain without www or path."""
        if not url:
            return ""
        try:
            parsed = urlparse(url.strip() if "://" in url else f"https://{url.strip()}")
            netloc = (parsed.netloc or "").lower().split(":")[0]
            netloc = re.sub(r"^www\d*\.", "", netloc)
            return netloc.strip()
        except Exception:
            return ""

    @staticmethod
    def normalize_company_name(name: str) -> str:
        """Normalize company name for fuzzy duplicate comparison."""
        if not name:
            return ""
        clean = re.sub(r"[^a-zA-Z0-9]", "", name.lower())
        # Remove common corporate suffixes
        for suffix in ["inc", "llc", "ltd", "corp", "co", "gmbh", "pvt"]:
            if clean.endswith(suffix) and len(clean) > len(suffix) + 3:
                clean = clean[:-len(suffix)]
        return clean

    @staticmethod
    def deduplicate_leads(
        leads: List[Dict[str, Any]],
        existing_emails: Optional[List[str]] = None,
        existing_websites: Optional[List[str]] = None,
        existing_company_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Cross-source deduplication in priority order:
        
        1. Normalized email
        2. Normalized domain
        3. Normalized company name + country
        """
        seen_emails: Set[str] = set(
            e.lower().strip() for e in (existing_emails or []) if e and e.strip()
        )
        seen_domains: Set[str] = set(
            SearchService.extract_clean_domain(w)
            for w in (existing_websites or [])
            if w and SearchService.extract_clean_domain(w)
        )
        seen_company_keys: Set[str] = set(
            existing_company_keys or []
        )

        unique_leads: List[Dict[str, Any]] = []

        for lead in leads:
            email = (lead.get("email") or "").lower().strip()
            website = lead.get("website") or ""
            domain = SearchService.extract_clean_domain(website)
            comp_norm = SearchService.normalize_company_name(lead.get("company_name", ""))
            country = (lead.get("country") or "").upper().strip()
            comp_key = f"{comp_norm}:{country}" if comp_norm and len(comp_norm) >= 3 else ""

            # 1. Check normalized email duplicate
            if email and email in seen_emails:
                continue

            # 2. Check normalized domain duplicate
            if domain and domain in seen_domains:
                continue

            # 3. Check normalized company name + country duplicate
            if comp_key and comp_key in seen_company_keys:
                continue

            # Validate or clear invalid email
            if email:
                if not SearchService.validate_email(email):
                    lead["email"] = ""
                else:
                    seen_emails.add(email)

            if domain:
                seen_domains.add(domain)

            if comp_key:
                seen_company_keys.add(comp_key)

            unique_leads.append(lead)

        return unique_leads

    def _fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch URL content safely with 8-second timeout."""
        try:
            resp = self.session.get(
                url,
                timeout=8,
                allow_redirects=True,
                headers=HTTP_HEADERS
            )
            content_type = resp.headers.get("Content-Type", "").lower()
            if resp.status_code == 200 and ("text" in content_type or "html" in content_type or not content_type):
                return resp.text
            return None
        except Exception:
            return None

    def enrich_website_email(
        self,
        website_url: str,
        stats: Optional[Dict[str, int]] = None
    ) -> str:
        """Scrape landing page and up to 5 contact subpages on the same domain."""
        if not website_url:
            return ""

        try:
            parsed_base = urlparse(website_url if "://" in website_url else f"https://{website_url}")
            if not parsed_base.scheme or not parsed_base.netloc:
                return ""
        except Exception:
            return ""

        base_netloc = parsed_base.netloc.lower()
        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

        visited_urls: Set[str] = set()
        discovered_emails: List[str] = []

        landing_url = website_url
        visited_urls.add(landing_url.rstrip("/"))
        if stats is not None and "websites_checked" in stats:
            stats["websites_checked"] += 1

        landing_html = self._fetch_url_content(landing_url)
        if landing_html:
            emails = self.extract_emails_from_html(landing_html)
            discovered_emails.extend(emails)

        best_email = self.select_best_email(discovered_emails)
        if best_email:
            return best_email

        candidate_urls: List[str] = []
        if landing_html:
            hrefs = re.findall(r'href=[\'"]([^\'"]+)[\'"]', landing_html, re.IGNORECASE)
            for href in hrefs:
                if any(kw in href.lower() for kw in ["contact", "about", "wholesale"]):
                    full_link = urljoin(base_origin, href)
                    try:
                        p_link = urlparse(full_link)
                        if p_link.netloc.lower() == base_netloc and p_link.scheme in ("http", "https"):
                            clean_link = full_link.split("#")[0].rstrip("/")
                            if clean_link not in visited_urls and clean_link not in candidate_urls:
                                candidate_urls.append(clean_link)
                    except Exception:
                        continue

        for subpath in CONTACT_SUBPATHS:
            target_url = urljoin(base_origin, subpath).rstrip("/")
            if target_url not in visited_urls and target_url not in candidate_urls:
                candidate_urls.append(target_url)

        for target_url in candidate_urls:
            if len(visited_urls) >= 5:
                break
            if target_url in visited_urls:
                continue

            visited_urls.add(target_url)
            if stats is not None and "contact_pages_checked" in stats:
                stats["contact_pages_checked"] += 1

            page_html = self._fetch_url_content(target_url)
            if page_html:
                page_emails = self.extract_emails_from_html(page_html)
                discovered_emails.extend(page_emails)
                best_email = self.select_best_email(discovered_emails)
                if best_email:
                    return best_email

        return self.select_best_email(discovered_emails)

    def enrich_leads_list(
        self,
        leads: List[Dict[str, Any]],
        stats_tracker: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """Multi-stage email enrichment using contact scraping and optional Hunter discovery."""
        if stats_tracker is None:
            stats_tracker = {
                "websites_checked": 0,
                "contact_pages_checked": 0,
                "emails_discovered": 0,
                "leads_without_email": 0,
                "hunter_checked": 0,
                "hunter_emails_found": 0,
            }

        for lead in leads:
            existing_email = (lead.get("email") or "").strip().lower()
            website = lead.get("website") or ""
            company_name = lead.get("company_name") or ""

            if existing_email and self.validate_email(existing_email):
                lead["email"] = existing_email
                stats_tracker["emails_discovered"] += 1
                continue

            discovered_email = ""

            # 1. Contact Page Scraping
            if website:
                discovered_email = self.enrich_website_email(website, stats=stats_tracker)

            # 2. Hunter.io API if configured and still missing email
            if not discovered_email and website and self.hunter_service and self.hunter_service.api_key:
                domain = HunterService.extract_clean_domain(website)
                if domain:
                    if "hunter_checked" in stats_tracker:
                        stats_tracker["hunter_checked"] += 1
                    hunter_email = self.hunter_service.find_email(domain, company_name=company_name)
                    if hunter_email and self.validate_email(hunter_email):
                        discovered_email = hunter_email
                        if "hunter_emails_found" in stats_tracker:
                            stats_tracker["hunter_emails_found"] += 1

            if discovered_email and self.validate_email(discovered_email):
                lead["email"] = discovered_email.lower().strip()
                stats_tracker["emails_discovered"] += 1
            else:
                lead["email"] = ""
                stats_tracker["leads_without_email"] += 1

        return leads

    def search_all_sources(
        self,
        query: str,
        country: str = "",
        limit: int = 10,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute buyer discovery across multiple configured B2B sources.

        Args:
            query: Base buyer search terms (e.g., 'Tibetan Singing Bowl').
            country: Target country code (e.g., 'US', 'DE', 'GB').
            limit: Limit per source.
            sources: List of source identifiers to query (defaults to all 8).

        Returns:
            Dict with:
                - sources: Dict of {source_name: {"status": ..., "found": ..., "reason": ...}}
                - raw_results: int
                - all_raw_leads: List[Dict[str, Any]]
        """
        # Dynamically sync Serper key with latest config
        if "serper" in self.sources:
            serper_src: SerperLeadSource = self.sources["serper"]  # type: ignore
            serper_src.api_key = self.api_key
            serper_src.api_url = self.api_url

        target_sources = [s.lower() for s in (sources or self.DEFAULT_SOURCES)]
        source_stats: Dict[str, Dict[str, Any]] = {}
        all_raw_leads: List[Dict[str, Any]] = []

        for src_name in target_sources:
            adapter = self.sources.get(src_name)
            if not adapter:
                source_stats[src_name] = {
                    "status": "unavailable",
                    "found": 0,
                    "reason": f"Unknown source adapter: {src_name}",
                }
                continue

            try:
                result = adapter.search(query=query, country=country, limit=limit)
                source_stats[src_name] = {
                    "status": result.get("status", "unavailable"),
                    "found": result.get("found", 0),
                    "reason": result.get("reason"),
                }
                if result.get("status") == "success" and result.get("leads"):
                    all_raw_leads.extend(result["leads"])
            except Exception as e:
                logger.error(f"Error querying source '{src_name}': {e}", exc_info=True)
                source_stats[src_name] = {
                    "status": "error",
                    "found": 0,
                    "reason": f"Source adapter error: {str(e)}",
                }

        return {
            "sources": source_stats,
            "raw_results": len(all_raw_leads),
            "all_raw_leads": all_raw_leads,
        }

    def search_leads(self, query: str, country: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        """Legacy compatibility wrapper for Serper-only search."""
        serper_adapter = self.sources.get("serper")
        if not serper_adapter:
            return []
        serper_adapter.api_key = self.api_key
        serper_adapter.api_url = self.api_url
        res = serper_adapter.search(query=query, country=country, limit=limit)
        return res.get("leads", [])
