"""Email Verification & Cross-Checking Service.

Performs multi-layer verification on discovered buyer emails:
1. RFC syntax validation
2. Anti-disposable and anti-temp mailbox filtering
3. Domain DNS / host resolvability check
4. Role and generic business mailbox detection
5. Overall deliverability & quality confidence scoring
"""

import re
import socket
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Common disposable and temporary email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "yopmail.com",
    "trashmail.com",
    "fakeinbox.com",
    "sharklasers.com",
    "throwawaymail.com",
    "getairmail.com",
    "dispostable.com",
    "tempm.com",
}

# Role-based prefix identifiers
ROLE_PREFIXES = (
    "sales",
    "wholesale",
    "orders",
    "info",
    "contact",
    "support",
    "admin",
    "office",
    "service",
    "export",
    "trade",
    "inquiries",
    "enquiries",
)


class VerificationService:
    """Multi-layer Email Cross-Checking and Validation Service."""

    @staticmethod
    def verify_syntax(email: str) -> bool:
        """Validate RFC compliance and TLD structure."""
        if not email or not isinstance(email, str):
            return False
        clean = email.strip().lower()
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, clean))

    @staticmethod
    def check_domain_dns(domain: str) -> bool:
        """Check if domain resolves via DNS."""
        if not domain:
            return False
        try:
            # Check host resolution
            socket.getaddrinfo(domain, 80, proto=socket.IPPROTO_TCP)
            return True
        except (socket.gaierror, socket.herror, Exception):
            return False

    @classmethod
    def verify_single_email(cls, email: str, check_dns: bool = True) -> Dict[str, Any]:
        """Perform full validation and cross-checking on a single email address."""
        if not email or not isinstance(email, str):
            return {
                "email": "",
                "is_valid": False,
                "syntax_valid": False,
                "domain_exists": False,
                "is_disposable": False,
                "is_role_account": False,
                "confidence": 0,
                "status": "INVALID",
                "reason": "Empty email string"
            }

        clean = email.strip().lower()
        syntax_ok = cls.verify_syntax(clean)

        if not syntax_ok:
            return {
                "email": clean,
                "is_valid": False,
                "syntax_valid": False,
                "domain_exists": False,
                "is_disposable": False,
                "is_role_account": False,
                "confidence": 0,
                "status": "INVALID",
                "reason": "Malformed syntax or invalid TLD"
            }

        local_part, domain_part = clean.split("@", 1)
        is_disposable = domain_part in DISPOSABLE_DOMAINS
        is_role = any(local_part == prefix or local_part.startswith(f"{prefix}.") for prefix in ROLE_PREFIXES)

        if is_disposable:
            return {
                "email": clean,
                "is_valid": False,
                "syntax_valid": True,
                "domain_exists": True,
                "is_disposable": True,
                "is_role_account": is_role,
                "confidence": 10,
                "status": "DISPOSABLE",
                "reason": "Disposable/temporary mailbox domain detected"
            }

        domain_ok = True
        if check_dns:
            domain_ok = cls.check_domain_dns(domain_part)

        confidence = 90 if domain_ok else 50
        if is_role:
            confidence = min(confidence + 5, 98)

        status = "VERIFIED" if (syntax_ok and domain_ok) else ("RISKY" if syntax_ok else "INVALID")

        return {
            "email": clean,
            "is_valid": syntax_ok and domain_ok and not is_disposable,
            "syntax_valid": syntax_ok,
            "domain_exists": domain_ok,
            "is_disposable": is_disposable,
            "is_role_account": is_role,
            "confidence": confidence,
            "status": status,
            "reason": "Format & domain verified" if (syntax_ok and domain_ok) else "Domain unresolvable"
        }

    @classmethod
    def verify_buyers_batch(cls, buyers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cross-check and verify a list of buyer leads."""
        results = []
        verified_count = 0
        invalid_count = 0
        empty_count = 0

        for b in buyers:
            email = (b.get("email") or "").strip().lower()
            if not email:
                empty_count += 1
                results.append({
                    "buyer_name": b.get("buyer_name", ""),
                    "company_name": b.get("company_name", ""),
                    "email": "",
                    "status": "NO_EMAIL",
                    "confidence": 0,
                })
            else:
                ver = cls.verify_single_email(email)
                if ver["is_valid"]:
                    verified_count += 1
                else:
                    invalid_count += 1
                results.append({
                    "buyer_name": b.get("buyer_name", ""),
                    "company_name": b.get("company_name", ""),
                    "email": email,
                    "status": ver["status"],
                    "confidence": ver["confidence"],
                    "reason": ver["reason"],
                })

        return {
            "total_checked": len(buyers),
            "verified_count": verified_count,
            "invalid_count": invalid_count,
            "empty_count": empty_count,
            "results": results,
        }
