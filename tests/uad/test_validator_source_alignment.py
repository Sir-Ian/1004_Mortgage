from __future__ import annotations

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


def test_alignment_passes_when_sources_match():
    payload = _base_payload()
    sources = {
        "subject": {
            "address": payload["subject"]["address"].copy(),
            "parcel_number": payload["subject"]["parcel_number"],
            "borrower_name": payload["subject"]["borrower_name"],
            "public_record_owner": payload["subject"]["public_record_owner"],
        },
        "contract": payload["contract"].copy(),
    }
    payload["sources"] = {
        "loan_docs": sources,
        "title": sources,
        "public_records": sources,
    }

    result = validate(payload, SCHEMA, REGISTRY)
    findings = [f for f in result["findings"] if f["rule"] == "R-06"]
    assert not findings
    assert result["status"] == "pass"


def test_alignment_flags_each_field_mismatch():
    payload = _base_payload()
    payload["sources"] = {
        "loan_docs": {
            "subject": {
                "address": {
                    "street": "123 Main Street",
                    "city": "Denver",
                    "state": "CO",
                    "zip": "80202",
                },
                "parcel_number": "1234567890",
                "borrower_name": "Alex Morgan",
                "public_record_owner": "Alex Morgan",
            },
            "contract": payload["contract"].copy(),
        },
        "title": {
            "subject": {
                "address": {
                    "street": "12 Diverge Ave",
                    "city": "Denver",
                    "state": "CO",
                    "zip": "80202",
                },
                "parcel_number": "1234567890",
                "borrower_name": "Taylor Morgan",
                "public_record_owner": "Taylor Morgan",
            },
            "contract": payload["contract"].copy(),
        },
        "public_records": {
            "subject": {
                "address": {
                    "street": "123 Main St",
                    "city": "Denver",
                    "state": "CO",
                    "zip": "80202",
                },
                "parcel_number": "1234567890",
                "borrower_name": "Alex Morgan",
                "public_record_owner": "Alex Morgan",
            },
            "contract": payload["contract"].copy(),
        },
    }

    result = validate(payload, SCHEMA, REGISTRY)
    findings = [f for f in result["findings"] if f["rule"] == "R-06"]
    assert {f["field"] for f in findings} == {
        "subject.address.street",
        "subject.borrower_name",
        "subject.public_record_owner",
    }
    assert all(f["severity"] == "error" for f in findings)
    street_finding = next(f for f in findings if f["field"] == "subject.address.street")
    assert "Loan docs" in street_finding["message"]
    assert street_finding["sources"]["title"]["value"] == "12 Diverge Ave"
    name_finding = next(f for f in findings if f["field"] == "subject.borrower_name")
    assert name_finding["sources"]["public_records"]["missing"] is False
    owner_finding = next(f for f in findings if f["field"] == "subject.public_record_owner")
    assert owner_finding["sources"]["title"]["value"] == "Taylor Morgan"
    assert result["status"] == "fail"
