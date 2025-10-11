from __future__ import annotations

from src.uad.validator import validate

SCHEMA = "schema/uad_1004_v1.json"
REGISTRY = "registry/fields.json"


def test_missing_required_flags_errors():
    payload = {
        "subject": {
            "address": {
                "street": "123 Main",
                "city": "Chicago",
                "state": "IL",
                "zip": "60601",
            },
            "pud_indicator": True,
            "tax_year": "2024",
            "real_estate_taxes": 3500,
        },
        "contract": {"assignment_type": "Purchase"},
    }
    result = validate(payload, SCHEMA, REGISTRY)
    fields = [finding["field"] for finding in result["findings"]]
    assert "contract.contract_price" in fields
    assert result["status"] == "fail"
