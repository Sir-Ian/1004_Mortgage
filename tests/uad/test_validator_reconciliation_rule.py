from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.uad.validator import validate

from .builders import REGISTRY_PATH, SCHEMA_PATH, base_payload


def _evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    return validate(payload, SCHEMA_PATH, REGISTRY_PATH)


def _findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in result["findings"] if f["rule"] == "R-12"]


def test_reconciliation_rule_allows_as_is() -> None:
    payload = base_payload()
    payload["reconciliation"] = {"appraisal_type": "As is"}

    result = _evaluate(payload)

    assert _findings(result) == []


def test_reconciliation_rule_flags_subject_to_without_review() -> None:
    payload = base_payload()
    payload["reconciliation"] = {"appraisal_type": "Subject to"}

    result = _evaluate(payload)

    findings = _findings(result)
    assert len(findings) == 1
    finding = findings[0]
    assert finding["severity"] == "condition"
    assert "Subject to" in finding["message"]


def test_reconciliation_rule_skips_when_escalated() -> None:
    payload = deepcopy(base_payload())
    payload["reconciliation"] = {
        "appraisal_type": "Subject to completion per plans",
    }
    payload["review"] = {"escalated": True}

    result = _evaluate(payload)

    assert _findings(result) == []
