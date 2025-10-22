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
    }


def test_reconciliation_rule_allows_as_is() -> None:
    payload = _base_payload()
    payload["reconciliation"] = {"appraisal_type": "As is"}

    result = validate(payload, SCHEMA, REGISTRY)

    findings = [f for f in result["findings"] if f["rule"] == "R-12"]
    assert findings == []


def test_reconciliation_rule_flags_subject_to_without_review() -> None:
    payload = _base_payload()
    payload["reconciliation"] = {"appraisal_type": "Subject to"}

    result = validate(payload, SCHEMA, REGISTRY)

    findings = [f for f in result["findings"] if f["rule"] == "R-12"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["severity"] == "condition"
    assert "Subject to" in finding["message"]


def test_reconciliation_rule_skips_when_escalated() -> None:
    payload = deepcopy(_base_payload())
    payload["reconciliation"] = {
        "appraisal_type": "Subject to completion per plans",
    }
    payload["review"] = {"escalated": True}

    result = validate(payload, SCHEMA, REGISTRY)

    findings = [f for f in result["findings"] if f["rule"] == "R-12"]
    assert findings == []
