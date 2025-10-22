from __future__ import annotations

from src.uad import RULESET_VERSION
from src.uad.validator import validate

from .builders import REGISTRY_PATH, SCHEMA_PATH, signed_report_payload


def test_signature_rule_errors_when_fields_missing() -> None:
    payload = signed_report_payload()
    payload.pop("photos")
    payload.pop("certifications")
    payload.pop("sections")
    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
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
    payload = signed_report_payload()
    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    assert all(f["rule"] != "R-01" for f in result["findings"])
    assert all(f["rule"] != "R-02" for f in result["findings"])
    assert result["status"] == "pass"
    assert result["ruleset_version"] == RULESET_VERSION


def test_signature_rule_skips_when_signature_absent() -> None:
    payload = signed_report_payload()
    payload["appraiser"] = {
        "signature_present": False,
        "signature_date": "03/02/2024",
    }
    payload.pop("photos")
    payload.pop("certifications")
    payload.pop("sections")
    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    assert all(f["rule"] != "R-01" for f in result["findings"])
    assert all(f["rule"] != "R-02" for f in result["findings"])


def test_signature_rule_skips_when_date_missing() -> None:
    payload = signed_report_payload()
    payload["appraiser"] = {
        "signature_present": True,
        "signature_date": None,
    }
    payload.pop("photos")
    payload.pop("certifications")
    payload.pop("sections")
    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    assert all(f["rule"] != "R-01" for f in result["findings"])
    assert all(f["rule"] != "R-02" for f in result["findings"])


def test_photo_rule_flags_missing_reference() -> None:
    payload = signed_report_payload()
    payload["photos"]["kitchen"]["reference"] = ""
    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    r02_findings = [f for f in result["findings"] if f["rule"] == "R-02"]
    assert len(r02_findings) == 1
    assert "Photos.Kitchen.Reference" in r02_findings[0]["message"]
    assert result["status"] == "fail"


def test_photo_rule_flags_missing_presence_boolean() -> None:
    payload = signed_report_payload()
    payload["photos"]["bathroom"]["present"] = False
    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)
    r02_findings = [f for f in result["findings"] if f["rule"] == "R-02"]
    assert len(r02_findings) == 1
    assert "Photos.Bathroom.Present" in r02_findings[0]["message"]
    assert result["status"] == "fail"
