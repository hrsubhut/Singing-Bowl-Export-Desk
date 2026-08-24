"""Gmail & Automated Personalized Email Dispatch Service.

Handles generating personalized Singing Bowl export outreach messages, attaching
product catalog PDFs, sending via Gmail SMTP, preventing re-contacting previously
contacted buyers, and recording dispatch logs.
"""

import os
import time
import uuid
import smtplib
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_SUBJECT_TEMPLATE = "Himalayan Handcrafted Singing Bowls Wholesale Export Catalog – Nepal Exporters"

DEFAULT_BODY_TEMPLATE = """Dear {buyer_name},

Greetings from Nepal!

We noticed that {company_name} is actively dealing in authentic meditation, wellness, and sound healing instruments in {country}.

We are a premier exporter and artisan cooperative specializing in authentic, hand-hammered Tibetan Singing Bowls, Bronze Meditation Bells, Tingsha Cymbals, and Chakra Healing Sets direct from Kathmandu, Nepal.

Why Partner With Us?
• Authentic 7-Metal Hand-Hammered Singing Bowls tuned to healing frequencies (432Hz / 528Hz)
• Competitive wholesale pricing direct from artisan workshops
• Full export compliance, international packing, and air-cargo logistics to {country}
• Custom laser engraving and artisan gift box packaging available

Please find our complete 2026 Singing Bowl Export Presentation & Wholesale Catalog attached as a PDF.

We would love to send you a complimentary sample set or discuss your wholesale volume requirements.

Warm regards,

Singing Bowl Export Desk
Export & International Trade Division
Kathmandu, Nepal
"""


class GmailService:
    """Service to handle automated personalized outreach and PDF catalog delivery via Gmail."""

    def __init__(
        self,
        user: str = "",
        password: str = "",
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
    ):
        self.user = user.strip() if user else ""
        self.password = password.strip() if password else ""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def is_configured(self) -> bool:
        """Check whether Gmail credentials are fully configured."""
        return bool(self.user and self.password)

    def personalize_text(
        self,
        template_str: str,
        buyer: Dict[str, Any]
    ) -> str:
        """Replace personalization tokens in template string."""
        if not template_str:
            return ""

        b_name = (buyer.get("buyer_name") or "").strip()
        c_name = (buyer.get("company_name") or "").strip()
        country = (buyer.get("country") or "").strip()

        display_buyer = b_name if b_name else (c_name if c_name else "Valued Partner")
        display_company = c_name if c_name else "your esteemed business"
        display_country = country if country else "your region"

        text = template_str.replace("{buyer_name}", display_buyer)
        text = text.replace("{company_name}", display_company)
        text = text.replace("{country}", display_country)
        text = text.replace("{email}", buyer.get("email", ""))
        text = text.replace("{website}", buyer.get("website", ""))

        return text

    def send_single_email(
        self,
        recipient_email: str,
        subject: str,
        body_text: str,
        catalog_path: Optional[str] = None,
        campaign_name: str = "Singing Bowl Export Outreach",
        buyer_name: str = "",
    ) -> Dict[str, Any]:
        """Send a single personalized email with optional PDF catalog attachment."""
        now_utc = datetime.now(timezone.utc).isoformat()
        clean_recipient = recipient_email.strip().lower()

        if not clean_recipient:
            return {
                "success": False,
                "status": "FAILED",
                "message_id": "",
                "error": "Recipient email address is missing or empty.",
                "timestamp": now_utc,
                "recipient": "",
                "catalog_file": os.path.basename(catalog_path) if catalog_path else "",
            }

        if not self.is_configured():
            logger.warning("Gmail credentials (GMAIL_USER / GMAIL_APP_PASSWORD) not configured in .env.")
            return {
                "success": False,
                "status": "FAILED",
                "message_id": "",
                "error": "GMAIL_USER or GMAIL_APP_PASSWORD is not configured in .env.",
                "timestamp": now_utc,
                "recipient": clean_recipient,
                "catalog_file": os.path.basename(catalog_path) if catalog_path else "",
            }

        # Build MIME Message
        msg = MIMEMultipart()
        msg["From"] = f"Singing Bowl Export Desk <{self.user}>"
        msg["To"] = clean_recipient
        msg["Subject"] = subject
        msg["Date"] = email_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg_id = f"<{uuid.uuid4()}@singingbowlexport.local>"
        msg["Message-ID"] = msg_id

        # Attach body plain text
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        catalog_filename = ""
        # Attach PDF catalog if present and accessible
        if catalog_path and os.path.isfile(catalog_path):
            catalog_filename = os.path.basename(catalog_path)
            try:
                with open(catalog_path, "rb") as f:
                    pdf_data = f.read()
                    pdf_attachment = MIMEApplication(pdf_data, _subtype="pdf")
                    pdf_attachment.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=catalog_filename
                    )
                    msg.attach(pdf_attachment)
            except Exception as e:
                logger.error(f"Failed to attach catalog PDF from {catalog_path}: {e}")

        # Send via SMTP_SSL
        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.login(self.user, self.password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {clean_recipient} (MsgID: {msg_id})")
            return {
                "success": True,
                "status": "SENT",
                "message_id": msg_id,
                "error": "",
                "timestamp": now_utc,
                "recipient": clean_recipient,
                "catalog_file": catalog_filename,
            }

        except smtplib.SMTPAuthenticationError as e:
            err_msg = f"Gmail SMTP Authentication failed. Check GMAIL_USER and App Password ({e})"
            logger.error(err_msg)
            return {
                "success": False,
                "status": "FAILED",
                "message_id": "",
                "error": err_msg,
                "timestamp": now_utc,
                "recipient": clean_recipient,
                "catalog_file": catalog_filename,
            }
        except (smtplib.SMTPException, Exception) as e:
            err_msg = f"Gmail SMTP delivery failed: {str(e)}"
            logger.error(err_msg)
            return {
                "success": False,
                "status": "FAILED",
                "message_id": "",
                "error": err_msg,
                "timestamp": now_utc,
                "recipient": clean_recipient,
                "catalog_file": catalog_filename,
            }

    def send_campaign(
        self,
        buyers: List[Dict[str, Any]],
        subject_template: Optional[str] = None,
        body_template: Optional[str] = None,
        catalog_path: Optional[str] = None,
        campaign_name: str = "Singing Bowl Export Outreach",
        previously_contacted_emails: Optional[Set[str]] = None,
        delay_seconds: float = 0.5,
    ) -> Dict[str, Any]:
        """Execute personalized bulk outreach with re-contact prevention.

        Args:
            buyers: List of buyer lead dicts.
            subject_template: Optional custom subject template with tokens.
            body_template: Optional custom body template with tokens.
            catalog_path: Path to uploaded catalog PDF.
            campaign_name: Campaign label.
            previously_contacted_emails: Set of lowercase emails already contacted.
            delay_seconds: Sleep interval between SMTP dispatches.

        Returns:
            Dict containing campaign results summary and dispatch logs.
        """
        subj_tmpl = subject_template or DEFAULT_SUBJECT_TEMPLATE
        body_tmpl = body_template or DEFAULT_BODY_TEMPLATE
        contacted_set = set(e.lower().strip() for e in (previously_contacted_emails or set()))

        sent_count = 0
        failed_count = 0
        skipped_count = 0
        dispatch_logs: List[Dict[str, Any]] = []

        for buyer in buyers:
            email = (buyer.get("email") or "").strip().lower()
            buyer_name = buyer.get("buyer_name", "")
            company_name = buyer.get("company_name", "")
            status = buyer.get("status", "").upper()

            # Skip leads without emails
            if not email:
                skipped_count += 1
                continue

            # Skip previously contacted leads (Rule 8: maintain history so already contacted buyers are not re-contacted)
            if email in contacted_set or status == "CONTACTED":
                skipped_count += 1
                logger.info(f"Skipping already contacted buyer: {email} ({company_name})")
                continue

            # Personalize subject and body
            personalized_subject = self.personalize_text(subj_tmpl, buyer)
            personalized_body = self.personalize_text(body_tmpl, buyer)

            # Send Email
            result = self.send_single_email(
                recipient_email=email,
                subject=personalized_subject,
                body_text=personalized_body,
                catalog_path=catalog_path,
                campaign_name=campaign_name,
                buyer_name=buyer_name,
            )

            log_entry = {
                "buyer_email": email,
                "buyer_name": buyer_name or company_name,
                "campaign_name": campaign_name,
                "catalog_file": result.get("catalog_file", ""),
                "sent_at": result.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "status": result.get("status", "FAILED"),
                "message_id": result.get("message_id") or result.get("error", "FAILED"),
            }
            dispatch_logs.append(log_entry)

            if result["success"]:
                sent_count += 1
                contacted_set.add(email)
                buyer["status"] = "CONTACTED"
            else:
                failed_count += 1

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        return {
            "success": True,
            "campaign_name": campaign_name,
            "total_targeted": len(buyers),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "logs": dispatch_logs,
        }
