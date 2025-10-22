from __future__ import annotations

from src.uad.validator import validate

SCHEMA = "schema/uad_1004_v1.json"
REGISTRY = "registry/fields.json"


def _base_payload() -> dict:
    return {
        "subject": {
            "address": {
                "street": "123 Main St",
                "city": "Denver",
                "state": "CO",
                "zip": "80202",
            },
            "pud_indicator": False,
            "tax_year": "2024",
            "real_estate_taxes": 2500,
        },
        "contract": {"assignment_type": "Refinance"},
    }


def test_refinance_names_match_passes():
    payload = _base_payload()
    payload["subject"]["borrower_name"] = "Alex Morgan"
    payload["subject"]["public_record_owner"] = "Alex Morgan"

    result = validate(payload, SCHEMA, REGISTRY)
    messages = [finding["message"] for finding in result["findings"]]
    assert not any("Refinance borrower" in message for message in messages)
    assert result["status"] == "pass"


def test_refinance_last_name_mismatch_flags_condition():
    payload = _base_payload()
    payload["subject"]["borrower_name"] = "Alex Morgan"
    payload["subject"]["public_record_owner"] = "Taylor Smith"

    result = validate(payload, SCHEMA, REGISTRY)
    findings = [f for f in result["findings"] if f["rule"] == "X010"]
    assert findings, "Expected refinance name mismatch finding"
    assert findings[0]["severity"] == "condition"
    assert "Borrower: Alex Morgan" in findings[0]["message"]
    assert "Public record owner: Taylor Smith" in findings[0]["message"]


def test_joint_borrowers_share_last_name_no_finding():
    payload = _base_payload()
    payload["subject"]["borrower_name"] = "Alex & Jamie Morgan"
    payload["subject"]["public_record_owner"] = "Jamie Morgan"

    result = validate(payload, SCHEMA, REGISTRY)
    findings = [f for f in result["findings"] if f["rule"] == "X010"]
    assert not findings
