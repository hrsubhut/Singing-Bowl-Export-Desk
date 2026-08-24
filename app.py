"""API 3 – EXPORT Automation System
Flask web application for Singing Bowl export business.
"""

import csv
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, send_file
import requests
from config import Config
from services.search_service import SearchService
from services.hunter_service import HunterService
from services.gemini_service import GeminiService, GeminiServiceError
from services.gmail_service import GmailService, DEFAULT_SUBJECT_TEMPLATE, DEFAULT_BODY_TEMPLATE
from services.verification_service import VerificationService

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Config.BASE_DIR / "templates"
STATIC_DIR = Config.BASE_DIR / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR)
)
app.config.from_object(Config)

# Ensure data and upload directories exist (safely handles local & Vercel /tmp)
try:
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # If running on Vercel, copy initial seed data to writable /tmp directory
    if os.getenv("VERCEL"):
        seed_data_dir = Config.BASE_DIR / "data"
        seed_buyers = seed_data_dir / "buyers.csv"
        seed_sent_log = seed_data_dir / "sent_log.csv"

        target_buyers = app.config["BUYERS_CSV"]
        target_sent = app.config["SENT_LOG_CSV"]

        if seed_buyers.is_file() and not target_buyers.is_file():
            shutil.copy2(str(seed_buyers), str(target_buyers))
        if seed_sent_log.is_file() and not target_sent.is_file():
            shutil.copy2(str(seed_sent_log), str(target_sent))
except Exception as init_err:
    logger.warning(f"Storage directory initialization notice: {init_err}")

# Initialize service instances
hunter_service = HunterService(api_key=app.config.get("HUNTER_API_KEY", ""))
search_service = SearchService(
    api_key=app.config.get("LEAD_SEARCH_API_KEY", ""),
    api_url=app.config.get("LEAD_SEARCH_API_URL", "https://google.serper.dev/search"),
    hunter_service=hunter_service
)
gemini_service = GeminiService(
    api_key=app.config.get("GEMINI_API_KEY", ""),
    model=app.config.get("GEMINI_MODEL", "gemini-3.6-flash")
)
gmail_service = GmailService(
    user=app.config.get("GMAIL_USER", ""),
    password=app.config.get("GMAIL_APP_PASSWORD", "")
)

BUYER_FIELDNAMES = [
    "buyer_name",
    "company_name",
    "email",
    "website",
    "country",
    "source_platform",
    "classification",
    "status",
    "created_at"
]

SENT_LOG_FIELDNAMES = [
    "buyer_email",
    "buyer_name",
    "campaign_name",
    "catalog_file",
    "sent_at",
    "status",
    "message_id"
]


def load_buyers_from_csv():
    """Helper to safely read buyers from the CSV storage."""
    buyers = []
    csv_path = app.config["BUYERS_CSV"]
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    buyers.append(row)
        except Exception as e:
            app.logger.warning(f"Failed to read buyers.csv: {e}")
    return buyers


def append_buyers_to_csv(new_buyers):
    """Append new buyer records to buyers.csv storage."""
    if not new_buyers:
        return
    csv_path = app.config["BUYERS_CSV"]
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    with open(csv_path, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BUYER_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for buyer in new_buyers:
            row = {field: buyer.get(field, "") for field in BUYER_FIELDNAMES}
            writer.writerow(row)


def save_all_buyers_to_csv(buyers):
    """Rewrite data/buyers.csv preserving the 9-column schema."""
    csv_path = app.config["BUYERS_CSV"]
    with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BUYER_FIELDNAMES)
        writer.writeheader()
        for buyer in buyers:
            row = {field: buyer.get(field, "") for field in BUYER_FIELDNAMES}
            writer.writerow(row)


def load_sent_log_from_csv():
    """Helper to safely read sent log from the CSV storage."""
    sent_logs = []
    csv_path = app.config["SENT_LOG_CSV"]
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sent_logs.append(row)
        except Exception as e:
            app.logger.warning(f"Failed to read sent_log.csv: {e}")
    return sent_logs


def append_sent_logs_to_csv(new_logs):
    """Append new campaign dispatch logs to sent_log.csv."""
    if not new_logs:
        return
    csv_path = app.config["SENT_LOG_CSV"]
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    with open(csv_path, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SENT_LOG_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for log in new_logs:
            row = {field: log.get(field, "") for field in SENT_LOG_FIELDNAMES}
            writer.writerow(row)


def compute_dashboard_stats(buyers, sent_logs):
    """Compute summary dashboard metrics."""
    total_leads = len(buyers)
    contacted = len([b for b in buyers if b.get("status", "").lower() == "contacted"])
    emails_sent = len([l for l in sent_logs if l.get("status", "").lower() in ("sent", "delivered")])
    failed = len([l for l in sent_logs if l.get("status", "").lower() in ("failed", "bounced")])

    return {
        "total_leads": total_leads,
        "contacted": contacted,
        "emails_sent": emails_sent,
        "failed": failed,
    }


def get_active_catalog_path():
    """Get absolute path to uploaded catalog PDF if it exists."""
    upload_dir = Path(app.config["UPLOAD_FOLDER"])
    catalog_pdf = upload_dir / "catalog.pdf"
    if catalog_pdf.is_file():
        return str(catalog_pdf)
    # Check for any PDF in upload directory
    pdfs = list(upload_dir.glob("*.pdf"))
    if pdfs:
        return str(pdfs[0])
    return None


@app.route("/", methods=["GET"])
def index():
    """Singing Bowl Export Desk Dashboard."""
    buyers = load_buyers_from_csv()
    sent_logs = load_sent_log_from_csv()
    stats = compute_dashboard_stats(buyers, sent_logs)
    catalog_path = get_active_catalog_path()
    catalog_name = os.path.basename(catalog_path) if catalog_path else None

    return render_template(
        "index.html",
        stats=stats,
        buyers=buyers,
        sent_logs=sent_logs,
        catalog_name=catalog_name,
        gmail_configured=gmail_service.is_configured(),
        default_subject=DEFAULT_SUBJECT_TEMPLATE,
        default_body=DEFAULT_BODY_TEMPLATE
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint returning JSON status."""
    return jsonify({
        "status": "healthy",
        "service": "API 3 - EXPORT Automation System",
        "desk": "Singing Bowl Export Desk",
        "version": "1.0.0",
        "environment": app.config.get("FLASK_ENV", "development"),
        "search_configured": bool(app.config.get("LEAD_SEARCH_API_KEY")),
        "hunter_configured": bool(app.config.get("HUNTER_API_KEY")),
        "gemini_configured": bool(app.config.get("GEMINI_API_KEY")),
        "gmail_configured": gmail_service.is_configured()
    }), 200


@app.route("/api/refresh-data", methods=["GET"])
def refresh_data_api():
    """Retrieve up-to-date buyers, sent logs, stats, and catalog info."""
    buyers = load_buyers_from_csv()
    sent_logs = load_sent_log_from_csv()
    stats = compute_dashboard_stats(buyers, sent_logs)
    catalog_path = get_active_catalog_path()
    catalog_name = os.path.basename(catalog_path) if catalog_path else None

    return jsonify({
        "success": True,
        "buyers": buyers,
        "sent_logs": sent_logs,
        "stats": stats,
        "catalog_name": catalog_name,
        "gmail_configured": gmail_service.is_configured(),
        "total_leads": len(buyers)
    }), 200


@app.route("/api/search", methods=["POST"])
def search_leads_api():
    """Endpoint to trigger multi-source lead discovery with cross-source deduplication and email enrichment."""
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    country = data.get("country", "").strip()
    limit = data.get("limit", 25)
    selected_sources = data.get("sources")

    if not query:
        return jsonify({"success": False, "error": "Search query is required."}), 400

    api_key = app.config.get("LEAD_SEARCH_API_KEY")
    if not api_key:
        return jsonify({
            "success": False,
            "error": "LEAD_SEARCH_API_KEY is not configured. Please add your Serper API key to your .env file."
        }), 400

    try:
        try:
            limit_int = int(limit)
        except (ValueError, TypeError):
            limit_int = 25

        hunter_service.api_key = app.config.get("HUNTER_API_KEY", "")
        search_service.api_key = api_key
        search_service.api_url = app.config.get("LEAD_SEARCH_API_URL", "https://google.serper.dev/search")
        search_service.hunter_service = hunter_service

        discovery_results = search_service.search_all_sources(
            query=query,
            country=country,
            limit=limit_int,
            sources=selected_sources
        )

        all_raw_leads = discovery_results.get("all_raw_leads", [])
        raw_results_count = discovery_results.get("raw_results", len(all_raw_leads))
        source_breakdown = discovery_results.get("sources", {})

        existing_buyers = load_buyers_from_csv()
        existing_emails = [b.get("email", "") for b in existing_buyers if b.get("email")]
        existing_websites = [b.get("website", "") for b in existing_buyers if b.get("website")]
        existing_company_keys = [
            f"{SearchService.normalize_company_name(b.get('company_name', ''))}:{(b.get('country') or '').upper()}"
            for b in existing_buyers
            if b.get("company_name")
        ]

        unique_leads = SearchService.deduplicate_leads(
            all_raw_leads,
            existing_emails=existing_emails,
            existing_websites=existing_websites,
            existing_company_keys=existing_company_keys
        )

        stats_tracker = {
            "websites_checked": 0,
            "contact_pages_checked": 0,
            "hunter_checked": 0,
            "hunter_emails_found": 0,
            "emails_discovered": 0,
            "leads_without_email": 0
        }

        enriched_new_leads = search_service.enrich_leads_list(unique_leads, stats_tracker=stats_tracker)

        for existing in existing_buyers:
            if not (existing.get("email") or "").strip() and (existing.get("website") or "").strip():
                discovered_email = search_service.enrich_website_email(existing["website"], stats=stats_tracker)
                if not discovered_email and hunter_service.api_key:
                    dom = HunterService.extract_clean_domain(existing["website"])
                    if dom:
                        discovered_email = hunter_service.find_email(dom, company_name=existing.get("company_name"))

                if discovered_email and SearchService.validate_email(discovered_email):
                    existing["email"] = discovered_email.lower().strip()
                    stats_tracker["emails_discovered"] += 1

        all_buyers = existing_buyers + enriched_new_leads
        save_all_buyers_to_csv(all_buyers)

        leads_with_email_count = len([l for l in enriched_new_leads if (l.get("email") or "").strip()])
        leads_without_email_count = len([l for l in enriched_new_leads if not (l.get("email") or "").strip()])

        return jsonify({
            "success": True,
            "sources": source_breakdown,
            "raw_results": raw_results_count,
            "search_results": raw_results_count,
            "unique_leads": len(unique_leads),
            "new_leads": len(enriched_new_leads),
            "count": len(enriched_new_leads),
            "leads_with_email": leads_with_email_count,
            "leads_without_email": leads_without_email_count,
            "emails_found": leads_with_email_count,
            "leads": enriched_new_leads,
            "all_buyers": all_buyers,
            "total_leads": len(all_buyers)
        }), 200

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        return jsonify({
            "success": False,
            "error": f"Search API returned error ({status_code}): {e.response.text if e.response is not None else str(e)}"
        }), 502
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Search API network connection failed: {str(e)}"
        }), 502
    except Exception as e:
        app.logger.error(f"Search endpoint error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500


@app.route("/api/verify-emails", methods=["POST"])
def verify_emails_api():
    """Cross-check and verify buyer lead email deliverability and syntax."""
    buyers = load_buyers_from_csv()
    if not buyers:
        return jsonify({
            "success": True,
            "message": "No buyer leads found to verify.",
            "total_checked": 0,
            "verified_count": 0,
            "invalid_count": 0,
            "results": []
        }), 200

    verification_data = VerificationService.verify_buyers_batch(buyers)
    return jsonify({
        "success": True,
        "message": f"Verification completed: {verification_data['verified_count']} verified, {verification_data['invalid_count']} invalid/unresolvable.",
        **verification_data
    }), 200


@app.route("/api/upload-catalog", methods=["POST"])
def upload_catalog_api():
    """Upload Singing Bowl export catalog PDF."""
    if "catalog_pdf" not in request.files and "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded. Please select a PDF file."}), 400

    file = request.files.get("catalog_pdf") or request.files.get("file")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "Empty filename."}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"success": False, "error": "Only PDF (.pdf) files are allowed for the export catalog."}), 400

    upload_dir = Path(app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / "catalog.pdf"

    try:
        file.save(str(target_path))
        file_size = os.path.getsize(str(target_path))
        size_kb = round(file_size / 1024, 1)

        return jsonify({
            "success": True,
            "filename": file.filename,
            "saved_as": "catalog.pdf",
            "size_kb": size_kb,
            "message": f"Catalog '{file.filename}' ({size_kb} KB) uploaded successfully."
        }), 200
    except Exception as e:
        app.logger.error(f"Catalog upload error: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to save catalog: {str(e)}"}), 500


@app.route("/api/catalog/status", methods=["GET"])
def catalog_status_api():
    """Check currently active catalog PDF status."""
    cat_path = get_active_catalog_path()
    if cat_path and os.path.exists(cat_path):
        size_kb = round(os.path.getsize(cat_path) / 1024, 1)
        mod_time = datetime.fromtimestamp(os.path.getmtime(cat_path), tz=timezone.utc).isoformat()
        return jsonify({
            "exists": True,
            "filename": os.path.basename(cat_path),
            "size_kb": size_kb,
            "updated_at": mod_time
        }), 200
    return jsonify({
        "exists": False,
        "filename": None,
        "size_kb": 0,
        "updated_at": None
    }), 200


@app.route("/api/campaign/send", methods=["POST"])
def send_campaign_api():
    """Launch automated personalized email outreach with catalog PDF attachment."""
    data = request.get_json() or {}
    target_filter = data.get("target_filter", "BUSINESS_ONLY").upper()
    selected_emails = [e.lower().strip() for e in data.get("selected_emails", []) if e]
    subject = data.get("subject", "").strip() or DEFAULT_SUBJECT_TEMPLATE
    body = data.get("body", "").strip() or DEFAULT_BODY_TEMPLATE
    attach_catalog = data.get("attach_catalog", True)
    campaign_name = data.get("campaign_name", "Singing Bowl Export Outreach").strip()

    # Re-sync Gmail credentials from config
    gmail_service.user = app.config.get("GMAIL_USER", "")
    gmail_service.password = app.config.get("GMAIL_APP_PASSWORD", "")

    if not gmail_service.is_configured():
        return jsonify({
            "success": False,
            "error": "GMAIL_USER and GMAIL_APP_PASSWORD are not configured in .env. Please configure your Gmail App Password to send live campaigns."
        }), 400

    catalog_path = get_active_catalog_path() if attach_catalog else None

    buyers = load_buyers_from_csv()
    if not buyers:
        return jsonify({"success": False, "error": "No buyers in database to send to."}), 400

    # Filter target audience
    if target_filter == "BUSINESS_ONLY":
        eligible_buyers = [b for b in buyers if b.get("classification") == "BUSINESS" and (b.get("email") or "").strip()]
    elif target_filter == "SELECTED":
        eligible_buyers = [b for b in buyers if (b.get("email") or "").strip().lower() in set(selected_emails)]
    else:  # ALL_WITH_EMAIL
        eligible_buyers = [b for b in buyers if (b.get("email") or "").strip()]

    if not eligible_buyers:
        return jsonify({
            "success": False,
            "error": f"No eligible buyer leads found for target filter '{target_filter}'. Ensure leads have valid emails and classification."
        }), 400

    # Load previously sent records to prevent contacting again (Rule 8)
    existing_sent = load_sent_log_from_csv()
    contacted_emails = set(l.get("buyer_email", "").lower().strip() for l in existing_sent if l.get("status") in ("SENT", "DELIVERED"))

    # Execute campaign
    campaign_result = gmail_service.send_campaign(
        buyers=eligible_buyers,
        subject_template=subject,
        body_template=body,
        catalog_path=catalog_path,
        campaign_name=campaign_name,
        previously_contacted_emails=contacted_emails
    )

    # Append new logs to sent_log.csv
    if campaign_result.get("logs"):
        append_sent_logs_to_csv(campaign_result["logs"])

    # Update buyers.csv status
    save_all_buyers_to_csv(buyers)

    # Compute updated stats
    all_sent_logs = load_sent_log_from_csv()
    stats = compute_dashboard_stats(buyers, all_sent_logs)

    return jsonify({
        "success": True,
        "campaign_name": campaign_name,
        "targeted": len(eligible_buyers),
        "sent": campaign_result["sent_count"],
        "failed": campaign_result["failed_count"],
        "skipped": campaign_result["skipped_count"],
        "logs": campaign_result["logs"],
        "stats": stats,
        "all_buyers": buyers,
        "all_sent_logs": all_sent_logs
    }), 200


@app.route("/api/campaign/logs", methods=["GET"])
def campaign_logs_api():
    """Retrieve full dispatch and campaign history logs."""
    logs = load_sent_log_from_csv()
    return jsonify({
        "success": True,
        "count": len(logs),
        "logs": logs
    }), 200


@app.route("/api/classify", methods=["POST"])
def classify_leads_api():
    """Classify pending buyer leads as BUSINESS, INDIVIDUAL, or UNKNOWN using Gemini API."""
    api_key = app.config.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return jsonify({
            "success": False,
            "error": "GEMINI_API_KEY is not configured in .env. Please provide a valid Gemini API key."
        }), 400

    buyers = load_buyers_from_csv()
    if not buyers:
        return jsonify({
            "success": True,
            "classified_count": 0,
            "message": "No buyer leads found in database.",
            "buyers": []
        }), 200

    eligible_leads = [
        b for b in buyers
        if (b.get("email") or "").strip() and b.get("classification") == "PENDING"
    ]

    if not eligible_leads:
        return jsonify({
            "success": True,
            "classified_count": 0,
            "message": "No pending leads with valid emails require classification.",
            "buyers": buyers
        }), 200

    try:
        gemini_service.api_key = api_key
        gemini_service.model = app.config.get("GEMINI_MODEL", "gemini-3.6-flash")

        classification_map = gemini_service.classify_leads_batch(eligible_leads)

        classified_count = 0
        for buyer in buyers:
            email_key = (buyer.get("email") or "").strip().lower()
            if email_key in classification_map:
                buyer["classification"] = classification_map[email_key]
                classified_count += 1

        save_all_buyers_to_csv(buyers)

        return jsonify({
            "success": True,
            "classified_count": classified_count,
            "buyers": buyers
        }), 200

    except GeminiServiceError as e:
        app.logger.error(f"Gemini service error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 502
    except Exception as e:
        app.logger.error(f"Unexpected error during classification: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Classification failed: {str(e)}"
        }), 500


@app.route("/api/export/buyers-csv", methods=["GET"])
def export_buyers_csv():
    """Download buyers.csv as a file."""
    csv_path = app.config["BUYERS_CSV"]
    if not os.path.exists(csv_path):
        save_all_buyers_to_csv([])
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return send_file(
        str(csv_path),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"singing_bowl_buyers_{today_str}.csv"
    )


@app.route("/api/export/sent-logs-csv", methods=["GET"])
def export_sent_logs_csv():
    """Download sent_log.csv as a file."""
    csv_path = app.config["SENT_LOG_CSV"]
    if not os.path.exists(csv_path):
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            f.write("buyer_email,buyer_name,campaign_name,catalog_file,sent_at,status,message_id\n")
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return send_file(
        str(csv_path),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"singing_bowl_campaign_sent_logs_{today_str}.csv"
    )


@app.route("/api/campaign/preview", methods=["POST"])
def preview_campaign_email_api():
    """Generate a preview of the personalized email subject and body for a sample or selected lead."""
    data = request.get_json() or {}
    subject_tmpl = data.get("subject", "").strip() or DEFAULT_SUBJECT_TEMPLATE
    body_tmpl = data.get("body", "").strip() or DEFAULT_BODY_TEMPLATE

    buyers = load_buyers_from_csv()
    sample_buyer = {
        "buyer_name": "Marcus Vance",
        "company_name": "Zenith Sound & Meditation Imports LLC",
        "country": "United States",
        "email": "marcus.vance@zenithsoundhealing.com",
        "website": "https://zenithsoundhealing.com"
    }

    # If buyers exist, use the first business/valid buyer as sample
    if buyers:
        biz_buyers = [b for b in buyers if b.get("classification") == "BUSINESS" and b.get("email")]
        sample_buyer = biz_buyers[0] if biz_buyers else buyers[0]

    pers_subject = gmail_service.personalize_text(subject_tmpl, sample_buyer)
    pers_body = gmail_service.personalize_text(body_tmpl, sample_buyer)
    catalog_path = get_active_catalog_path()

    return jsonify({
        "success": True,
        "sample_buyer": sample_buyer,
        "subject": pers_subject,
        "body": pers_body,
        "catalog_attached": os.path.basename(catalog_path) if catalog_path else None
    }), 200


@app.route("/api/campaign/test-send", methods=["POST"])
def send_test_email_api():
    """Send a single sample test email directly to the configured GMAIL_USER account."""
    data = request.get_json() or {}
    subject = data.get("subject", "").strip() or DEFAULT_SUBJECT_TEMPLATE
    body = data.get("body", "").strip() or DEFAULT_BODY_TEMPLATE
    attach_catalog = data.get("attach_catalog", True)
    custom_recipient = data.get("test_email", "").strip()

    gmail_service.user = app.config.get("GMAIL_USER", "")
    gmail_service.password = app.config.get("GMAIL_APP_PASSWORD", "")

    if not gmail_service.is_configured():
        return jsonify({
            "success": False,
            "error": "GMAIL_USER and GMAIL_APP_PASSWORD are not configured in .env."
        }), 400

    target_email = custom_recipient if custom_recipient else gmail_service.user
    catalog_path = get_active_catalog_path() if attach_catalog else None

    # Sample lead data for test preview
    sample_buyer = {
        "buyer_name": "Export Partner (Test Preview)",
        "company_name": "Sample Wellness Importers LLC",
        "country": "United States",
        "email": target_email,
        "website": "https://sampleimporter.com"
    }

    pers_subject = "[SAMPLE TEST PREVIEW] " + gmail_service.personalize_text(subject, sample_buyer)
    pers_body = gmail_service.personalize_text(body, sample_buyer)

    res = gmail_service.send_single_email(
        recipient_email=target_email,
        subject=pers_subject,
        body_text=pers_body,
        catalog_path=catalog_path,
        campaign_name="Test Email Preview",
        buyer_name=sample_buyer["buyer_name"]
    )

    if res["success"]:
        return jsonify({
            "success": True,
            "recipient": target_email,
            "message": f"Sample test email successfully delivered to {target_email}! Check your inbox."
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": res.get("error", "Failed to dispatch test email.")
        }), 500


if __name__ == "__main__":
    port = app.config.get("PORT", 5000)
    debug = app.config.get("DEBUG", True)
    app.run(host="0.0.0.0", port=port, debug=debug)
