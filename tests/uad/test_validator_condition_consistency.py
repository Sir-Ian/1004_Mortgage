from __future__ import annotations

from src.uad.conditions import CONDITION_RANKS
from src.uad.validator import validate

SCHEMA = "schema/uad_1004_v1.json"
REGISTRY = "registry/fields.json"


def _base_payload() -> dict[str, object]:
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


def _subject_condition(code: str) -> dict[str, int | str]:
    return {"condition": code, "condition_rank": CONDITION_RANKS[code]}


def _comparable(code: str, ident: str) -> dict[str, int | str]:
    return {
        "id": ident,
        "condition": code,
        "condition_rank": CONDITION_RANKS[code],
    }


def _evaluate(payload: dict[str, object]):
    return validate(payload, SCHEMA, REGISTRY)


def _condition_findings(result: dict[str, object]):
    return [finding for finding in result["findings"] if finding["rule"] == "R-13"]


def test_condition_rule_passes_within_tolerance():
    payload = _base_payload()
    payload["sales_comparison"] = {
        "subject": _subject_condition("C3"),
        "comparables": [
            _comparable("C2", "Comp1"),
            _comparable("C3", "Comp2"),
            _comparable("C4", "Comp3"),
        ],
    }

    result = _evaluate(payload)
    assert not _condition_findings(result)
    assert result["status"] == "pass"


def test_condition_rule_allows_boundary_tolerance():
    payload = _base_payload()
    payload["sales_comparison"] = {
        "subject": _subject_condition("C4"),
        "comparables": [
            _comparable("C2", "Comp1"),
            _comparable("C4", "Comp2"),
        ],
    }

    result = _evaluate(payload)
    assert not _condition_findings(result)
    assert result["status"] == "pass"


def test_condition_rule_flags_outliers():
    payload = _base_payload()
    payload["sales_comparison"] = {
        "subject": _subject_condition("C5"),
        "comparables": [
            _comparable("C2", "Comp1"),
            _comparable("C2", "Comp2"),
        ],
    }

    result = _evaluate(payload)
    findings = _condition_findings(result)
    assert len(findings) == 2
    assert all(finding["severity"] == "error" for finding in findings)
    assert all("Δ=3.00" in finding["message"] for finding in findings)
    assert result["status"] == "fail"
