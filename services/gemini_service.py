"""Gemini AI Service for Lead Intelligence and Classification.

Uses the official google-genai SDK to classify Singing Bowl buyer leads
as BUSINESS, INDIVIDUAL, or UNKNOWN using structured JSON responses.
"""

import json
import logging
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)


class ClassificationType(str, Enum):
    BUSINESS = "BUSINESS"
    INDIVIDUAL = "INDIVIDUAL"
    UNKNOWN = "UNKNOWN"


class LeadClassificationResult(BaseModel):
    email: str = Field(description="The exact email address of the evaluated lead.")
    classification: ClassificationType = Field(
        description="Classification label: BUSINESS, INDIVIDUAL, or UNKNOWN."
    )


class BatchClassificationOutput(BaseModel):
    classifications: List[LeadClassificationResult] = Field(
        description="List of classified lead objects."
    )


class GeminiServiceError(Exception):
    """Custom exception for Gemini service failures."""
    pass


class GeminiService:
    """Service to handle Gemini AI-driven lead classification and outreach tasks."""

    def __init__(self, api_key: str = "", model: str = "gemini-3.6-flash"):
        self.api_key = api_key
        raw = model or "gemini-3.6-flash"
        self.model = "gemini-3.6-flash" if raw == "gemini-2.5-flash" else raw
        self._client: Optional[genai.Client] = None

    def get_client(self) -> genai.Client:
        """Initialize or return the google-genai Client."""
        if not self.api_key:
            raise GeminiServiceError(
                "GEMINI_API_KEY is not configured in application environment. "
                "Please provide a valid Gemini API key in your .env file."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def classify_leads_batch(self, leads: List[Dict[str, Any]]) -> Dict[str, str]:
        """Classify a list of buyer leads in batches of up to 20 leads.

        Args:
            leads: List of buyer dictionaries from buyers.csv.

        Returns:
            Dict mapping normalized email (lowercase) -> classification string ('BUSINESS', 'INDIVIDUAL', 'UNKNOWN').

        Raises:
            GeminiServiceError: If API call, authentication, rate limits, or response parsing fails.
        """
        # Filter eligible leads: non-empty email and classification == "PENDING"
        eligible_leads = [
            lead for lead in leads
            if (lead.get("email") or "").strip() and lead.get("classification") == "PENDING"
        ]

        if not eligible_leads:
            logger.info("No pending leads with valid emails found for Gemini classification.")
            return {}

        client = self.get_client()
        classification_results: Dict[str, str] = {}
        batch_size = 20

        for i in range(0, len(eligible_leads), batch_size):
            chunk = eligible_leads[i:i + batch_size]
            chunk_results = self._process_batch_chunk(client, chunk)
            classification_results.update(chunk_results)

        return classification_results

    def _process_batch_chunk(
        self,
        client: genai.Client,
        chunk: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Process a single batch chunk (<= 20 leads) with Gemini."""
        # Prepare structured input payload for the model
        leads_payload = []
        for lead in chunk:
            leads_payload.append({
                "buyer_name": lead.get("buyer_name", "").strip(),
                "company_name": lead.get("company_name", "").strip(),
                "email": lead.get("email", "").strip(),
                "website": lead.get("website", "").strip(),
                "country": lead.get("country", "").strip(),
                "source_platform": lead.get("source_platform", "").strip(),
            })

        system_prompt = (
            "You are an expert B2B trade intelligence assistant for a Himalayan / Tibetan Singing Bowl export business.\n"
            "Your task is to classify each potential buyer contact into exactly one of three categories:\n\n"
            "1. BUSINESS:\n"
            "   - Commercial companies, wholesale importers, distributors, retailers, sound healing studios, "
            "meditation centers, yoga supplies stores, gift shops, or corporate organizations.\n\n"
            "2. INDIVIDUAL:\n"
            "   - Clearly personal individual consumers or private hobbyists.\n"
            "   - NOTE: Having a personal email provider (e.g., @gmail.com, @yahoo.com) alone is NOT sufficient "
            "to classify as INDIVIDUAL if the company name, website, or title indicates a business, studio, or practitioner.\n\n"
            "3. UNKNOWN:\n"
            "   - Insufficient evidence to determine whether the lead is a business or individual.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Do NOT invent, assume, or fabricate any facts not provided in the input.\n"
            "- Return a structured JSON response matching the provided schema with an entry for every lead's email.\n"
        )

        user_content = (
            f"Classify the following {len(leads_payload)} buyer leads based strictly on their supplied data:\n\n"
            f"{json.dumps(leads_payload, indent=2)}"
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=BatchClassificationOutput,
            temperature=0.1,
        )

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=user_content,
                config=config,
            )

            if not response or not response.text:
                raise GeminiServiceError("Gemini API returned an empty response.")

            # Validate structured response using Pydantic
            try:
                parsed_output = BatchClassificationOutput.model_validate_json(response.text)
            except (ValidationError, json.JSONDecodeError) as parse_err:
                logger.error(f"Malformed Gemini classification JSON: {response.text}")
                raise GeminiServiceError(
                    f"Gemini API returned a malformed response format: {parse_err}"
                ) from parse_err

            chunk_map: Dict[str, str] = {}
            for item in parsed_output.classifications:
                norm_email = item.email.strip().lower()
                chunk_map[norm_email] = item.classification.value

            return chunk_map

        except APIError as api_err:
            logger.error(f"Gemini API Error: {api_err}", exc_info=True)
            raise GeminiServiceError(f"Gemini API error: {api_err.message}") from api_err
        except GeminiServiceError:
            raise
        except Exception as err:
            logger.error(f"Unexpected error during Gemini classification: {err}", exc_info=True)
            raise GeminiServiceError(f"Unexpected error communicating with Gemini API: {err}") from err

    def generate_personalized_pitch(self, buyer_name: str, company_name: str, catalog_title: str) -> str:
        """Placeholder for personalized outreach message generation in future step."""
        return ""
