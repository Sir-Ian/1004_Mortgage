from __future__ import annotations

from typing import Any

from src.uad.validator import validate

from .builders import REGISTRY_PATH, SCHEMA_PATH, base_payload, refinance_payload


def _findings(result: dict[str, Any], rule: str) -> list[dict[str, Any]]:
    return [finding for finding in result["findings"] if finding["rule"] == rule]


def test_schema_missing_contract_reports_error() -> None:
    payload = base_payload()
    payload.pop("contract")

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)

    findings = _findings(result, "schema")
    assert findings, "Expected schema findings when contract section is missing"
    assert findings[0]["field"] == "$"
    assert "contract" in findings[0]["message"].lower()
    assert result["status"] == "fail"


def test_requirement_triggers_for_purchase_assignment() -> None:
    payload = base_payload()
    payload["contract"].pop("contract_price")
    payload["contract"].pop("contract_date")

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)

    findings = _findings(result, "uad_requirement")
    assert {f["field"] for f in findings} == {
        "contract.contract_price",
        "contract.contract_date",
    }
    assert all(f["severity"] == "error" for f in findings)
    assert result["status"] == "fail"


def test_requirement_skips_for_refinance_assignment() -> None:
    payload = refinance_payload()
    payload["contract"].pop("contract_price", None)
    payload["contract"].pop("contract_date", None)

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)

    findings = _findings(result, "uad_requirement")
    assert findings == []
    assert result["status"] == "pass"


def test_cross_rule_warns_when_pud_missing_hoa_frequency() -> None:
    payload = base_payload()
    payload["subject"]["pud_indicator"] = True
    payload["subject"]["hoa_frequency"] = "None"

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)

    findings = _findings(result, "X002")
    assert len(findings) == 1
    assert findings[0]["severity"] == "warn"
    assert "hoa" in findings[0]["message"].lower()


def test_cross_rule_passes_when_hoa_frequency_present() -> None:
    payload = base_payload()
    payload["subject"]["pud_indicator"] = True
    payload["subject"]["hoa_frequency"] = "PerMonth"

    result = validate(payload, SCHEMA_PATH, REGISTRY_PATH)

    assert not _findings(result, "X002")
