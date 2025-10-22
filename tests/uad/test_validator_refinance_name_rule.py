from __future__ import annotations

from src.uad.validator import validate

from .builders import REGISTRY_PATH, SCHEMA_PATH, refinance_payload


def test_refinance_names_match_passes():
    payload = refinance_payload()
    payload["subject"]["borrower_name"] = "Alex Morgan"
    payload["subject"]["public_record_owner"] = "Alex Morgan"

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    messages = [finding["message"] for finding in result["findings"]]
    assert not any("Refinance borrower" in message for message in messages)
    assert result["status"] == "pass"


def test_refinance_last_name_mismatch_flags_condition():
    payload = refinance_payload()
    payload["subject"]["borrower_name"] = "Alex Morgan"
    payload["subject"]["public_record_owner"] = "Taylor Smith"

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    findings = [f for f in result["findings"] if f["rule"] == "X010"]
    assert findings, "Expected refinance name mismatch finding"
    assert findings[0]["severity"] == "condition"
    assert "Borrower: Alex Morgan" in findings[0]["message"]
    assert "Public record owner: Taylor Smith" in findings[0]["message"]


def test_joint_borrowers_share_last_name_no_finding():
    payload = refinance_payload()
    payload["subject"]["borrower_name"] = "Alex & Jamie Morgan"
    payload["subject"]["public_record_owner"] = "Jamie Morgan"

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    findings = [f for f in result["findings"] if f["rule"] == "X010"]
    assert not findings
