from __future__ import annotations

from copy import deepcopy

from src.uad.validator import validate

SCHEMA = "schema/uad_1004_v1.json"
REGISTRY = "registry/fields.json"


def _base_payload() -> dict[str, object]:
    return {
        "subject": {
            "address": {
                "street": "123 Main",
                "city": "Chicago",
                "state": "IL",
                "zip": "60601",
            },
            "pud_indicator": False,
            "tax_year": "2024",
            "real_estate_taxes": 3500,
        },
        "contract": {
            "assignment_type": "Purchase",
            "contract_price": 450000,
            "contract_date": "03/01/2024",
        },
        "appraiser": {
            "signature_present": True,
            "signature_date": "03/02/2024",
        },
    }


def _with_signature_dependencies(payload: dict[str, object]) -> dict[str, object]:
    enriched = deepcopy(payload)
    enriched.setdefault("photos", {})
    enriched["photos"] = {
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
    enriched["certifications"] = {
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
    enriched["sections"] = {
        "section_a": {"title": "Neighborhood", "page_number": 9, "comments": "Complete"},
        "section_b": {"title": "Site", "page_number": 10, "comments": "Complete"},
        "section_c": {"title": "Improvements", "page_number": 11, "comments": "Complete"},
        "section_d": {"title": "Additional Comments", "page_number": 12, "comments": "Complete"},
    }
    return enriched


def test_signature_rule_errors_when_fields_missing() -> None:
    payload = _base_payload()
    result = validate(payload, SCHEMA, REGISTRY)
    findings = result["findings"]
    r01_findings = [f for f in findings if f["rule"] == "R-01"]
    assert len(r01_findings) == 1
    finding = r01_findings[0]
    assert finding["field"] == "certifications.appraiser.name"
    assert "Sections A–D" in finding["message"]
    assert finding["severity"] == "error"
    r02_findings = [f for f in findings if f["rule"] == "R-02"]
    assert len(r02_findings) == 1
    assert "Photos." in r02_findings[0]["message"]
    assert r02_findings[0]["severity"] == "error"
    assert result["status"] == "fail"


def test_signature_rule_passes_when_fields_present() -> None:
    payload = _with_signature_dependencies(_base_payload())
    result = validate(payload, SCHEMA, REGISTRY)
    assert all(f["rule"] != "R-01" for f in result["findings"])
    assert all(f["rule"] != "R-02" for f in result["findings"])
    assert result["status"] == "pass"
    assert result["ruleset_version"] == "1.1.0"


def test_signature_rule_skips_when_signature_absent() -> None:
    payload = _base_payload()
    payload["appraiser"] = {
        "signature_present": False,
        "signature_date": "03/02/2024",
    }
    result = validate(payload, SCHEMA, REGISTRY)
    assert all(f["rule"] != "R-01" for f in result["findings"])
    assert all(f["rule"] != "R-02" for f in result["findings"])


def test_signature_rule_skips_when_date_missing() -> None:
    payload = _base_payload()
    payload["appraiser"] = {
        "signature_present": True,
        "signature_date": None,
    }
    result = validate(payload, SCHEMA, REGISTRY)
    assert all(f["rule"] != "R-01" for f in result["findings"])
    assert all(f["rule"] != "R-02" for f in result["findings"])


def test_photo_rule_flags_missing_reference() -> None:
    payload = _with_signature_dependencies(_base_payload())
    payload["photos"]["kitchen"]["reference"] = ""
    result = validate(payload, SCHEMA, REGISTRY)
    r02_findings = [f for f in result["findings"] if f["rule"] == "R-02"]
    assert len(r02_findings) == 1
    assert "Photos.Kitchen.Reference" in r02_findings[0]["message"]
    assert result["status"] == "fail"


def test_photo_rule_flags_missing_presence_boolean() -> None:
    payload = _with_signature_dependencies(_base_payload())
    payload["photos"]["bathroom"]["present"] = False
    result = validate(payload, SCHEMA, REGISTRY)
    r02_findings = [f for f in result["findings"] if f["rule"] == "R-02"]
    assert len(r02_findings) == 1
    assert "Photos.Bathroom.Present" in r02_findings[0]["message"]
    assert result["status"] == "fail"
