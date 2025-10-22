from __future__ import annotations

from typing import Any

from src.uad.conditions import CONDITION_RANKS
from src.uad.validator import validate

from .builders import REGISTRY_PATH, SCHEMA_PATH, base_payload, sales_comparison_payload


def _subject_condition(code: str) -> dict[str, Any]:
    return {"condition": code, "condition_rank": CONDITION_RANKS[code]}


def _comparable(code: str, ident: str) -> dict[str, Any]:
    return {
        "id": ident,
        "condition": code,
        "condition_rank": CONDITION_RANKS[code],
    }


def _evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    return validate(payload, SCHEMA_PATH, REGISTRY_PATH)


def _condition_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for finding in result["findings"] if finding["rule"] == "R-13"]


def test_condition_rule_passes_within_tolerance() -> None:
    payload = sales_comparison_payload(
        base_payload(),
        subject=_subject_condition("C3"),
        comparables=[
            _comparable("C2", "Comp1"),
            _comparable("C3", "Comp2"),
            _comparable("C4", "Comp3"),
        ],
    )

    result = _evaluate(payload)
    assert not _condition_findings(result)
    assert result["status"] == "pass"


def test_condition_rule_allows_boundary_tolerance() -> None:
    payload = sales_comparison_payload(
        base_payload(),
        subject=_subject_condition("C4"),
        comparables=[
            _comparable("C2", "Comp1"),
            _comparable("C4", "Comp2"),
        ],
    )

    result = _evaluate(payload)
    assert not _condition_findings(result)
    assert result["status"] == "pass"


def test_condition_rule_flags_outliers() -> None:
    payload = sales_comparison_payload(
        base_payload(),
        subject=_subject_condition("C5"),
        comparables=[
            _comparable("C2", "Comp1"),
            _comparable("C2", "Comp2"),
        ],
    )

    result = _evaluate(payload)
    findings = _condition_findings(result)
    assert len(findings) == 2
    assert all(finding["severity"] == "error" for finding in findings)
    assert all("Δ=3.00" in finding["message"] for finding in findings)
    assert result["status"] == "fail"
