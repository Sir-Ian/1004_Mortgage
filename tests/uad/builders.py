from __future__ import annotations

from copy import deepcopy
from typing import Any

SCHEMA_PATH = "schema/uad_1004_v1.json"
REGISTRY_PATH = "registry/fields.json"


def base_payload() -> dict[str, Any]:
    """Return a minimal payload that satisfies the schema subject + contract scaffolding."""

    return {
        "subject": {
            "address": {
                "street": "123 Main St",
                "city": "Denver",
                "state": "CO",
                "zip": "80202",
            },
            "parcel_number": "1234567890",
            "pud_indicator": False,
            "hoa_frequency": "None",
            "tax_year": "2024",
            "real_estate_taxes": 2400,
            "borrower_name": "Alex Morgan",
            "public_record_owner": "Alex Morgan",
        },
        "contract": {
            "assignment_type": "Purchase",
            "contract_price": 525000,
            "contract_date": "04/01/2024",
        },
    }


def refinance_payload() -> dict[str, Any]:
    payload = base_payload()
    payload["contract"]["assignment_type"] = "Refinance"
    return payload


def signed_report_payload() -> dict[str, Any]:
    payload = base_payload()
    payload["appraiser"] = {
        "signature_present": True,
        "signature_date": "03/02/2024",
    }
    payload["photos"] = {
        "front_exterior": {
            "caption": "Front",
            "page_number": 2,
            "present": True,
            "reference": "https://example.com/photos/front.jpg",
        },
        "rear_exterior": {
            "caption": "Rear",
            "page_number": 3,
            "present": True,
            "reference": "https://example.com/photos/rear.jpg",
        },
        "street_scene": {
            "caption": "Street",
            "page_number": 4,
            "present": True,
            "reference": "https://example.com/photos/street.jpg",
        },
        "kitchen": {
            "caption": "Kitchen",
            "page_number": 5,
            "present": True,
            "reference": "https://example.com/photos/kitchen.jpg",
        },
        "bathroom": {
            "caption": "Bathroom",
            "page_number": 6,
            "present": True,
            "reference": "https://example.com/photos/bathroom.jpg",
        },
        "living_room": {
            "caption": "Living",
            "page_number": 7,
            "present": True,
            "reference": "https://example.com/photos/living.jpg",
        },
        "other": {
            "caption": "Garage",
            "page_number": 8,
            "present": True,
            "reference": "https://example.com/photos/other.jpg",
        },
    }
    payload["certifications"] = {
        "appraiser": {
            "name": "Casey Appraiser",
            "license_number": "A12345",
            "state": "IL",
            "expiration_date": "12/31/2025",
        },
        "supervisory_appraiser": {
            "name": "Sam Supervisor",
            "license_number": "S67890",
            "state": "IL",
            "expiration_date": "11/30/2025",
        },
    }
    payload["sections"] = {
        "section_a": {"title": "Neighborhood", "page_number": 9, "comments": "Complete"},
        "section_b": {"title": "Site", "page_number": 10, "comments": "Complete"},
        "section_c": {"title": "Improvements", "page_number": 11, "comments": "Complete"},
        "section_d": {
            "title": "Additional Comments",
            "page_number": 12,
            "comments": "Complete",
        },
    }
    return payload


def duplicate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(payload)


def with_sources(
    payload: dict[str, Any],
    loan_docs: dict[str, Any] | None = None,
    title: dict[str, Any] | None = None,
    public_records: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = duplicate_payload(payload)
    sources: dict[str, Any] = {}
    if loan_docs is not None:
        sources["loan_docs"] = loan_docs
    if title is not None:
        sources["title"] = title
    if public_records is not None:
        sources["public_records"] = public_records
    if sources:
        enriched["sources"] = sources
    return enriched


def sales_comparison_payload(
    payload: dict[str, Any], subject: dict[str, Any], comparables: list[dict[str, Any]]
) -> dict[str, Any]:
    enriched = duplicate_payload(payload)
    enriched.setdefault("sales_comparison", {})
    enriched["sales_comparison"] = {
        "subject": subject,
        "comparables": comparables,
    }
    return enriched
