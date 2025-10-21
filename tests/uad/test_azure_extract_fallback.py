from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.uad.azure_extract import ExtractionResult, extract_1004_fields


@pytest.mark.parametrize("fallback_env", [True, False])
def test_extract_uses_fallback_when_azure_fails(tmp_path, monkeypatch, fallback_env):
    payload = {
        "payload": {
            "subject": {
                "address": {
                    "street": "100 Test St",
                    "city": "Austin",
                    "state": "TX",
                    "zip": "78701",
                },
                "pud_indicator": False,
            },
            "contract": {"assignment_type": "Purchase"},
            "appraiser": {
                "name": "Taylor Appraiser",
                "phone": "512-555-0184",
            },
        },
        "raw_fields": {
            "Subject.PropertyAddress.street": {
                "type": "string",
                "value": "100 Test St",
                "content": "100 Test St",
                "confidence": 0.93,
                "leaf": True,
            },
            "Subject.HoaPaymentInterval": {
                "type": "selectionGroup",
                "value": "(None Selected)",
                "content": "(None Selected)",
                "confidence": 0.45,
                "leaf": True,
            },
        },
        "missing_fields": [],
        "low_confidence_fields": ["Subject.HoaPaymentInterval"],
        "business_flags": [
            {
                "field": "Subject.HoaPaymentInterval",
                "issue": "none_selected",
                "message": "Azure Document Intelligence returned '(None Selected)' for this field.",
            }
        ],
        "model_id": "fallback-test",
        "fallback_used": True,
        "raw_payload": {
            "subject": {"AssessorParcelNumber": "100-ABC"},
            "photos": {"FrontExterior": {"Caption": "Front"}},
        },
    }
    fallback_path = tmp_path / "fallback.json"
    fallback_path.write_text(json.dumps(payload), encoding="utf-8")

    # Required env vars for client factory
    monkeypatch.setenv("AZURE_DOCINTEL_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AZURE_DOCINTEL_KEY", "key")
    monkeypatch.setenv("AZURE_DOCINTEL_MODEL_ID", "model-id")

    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\\n%mock document\\n")

    class DummyClient:
        def begin_analyze_document(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.uad.azure_extract._client", lambda: DummyClient())

    if fallback_env:
        monkeypatch.setenv("AZURE_DOCINTEL_FALLBACK_JSON", str(fallback_path))
    else:
        monkeypatch.setattr("src.uad.azure_extract._fallback_path", lambda: fallback_path)

    result = extract_1004_fields(str(pdf_path))
    assert isinstance(result, ExtractionResult)
    assert result.fallback_used is True
    assert result.payload == payload["payload"]
    assert result.raw_fields["Subject.PropertyAddress.street"]["value"] == "100 Test St"
    assert result.business_flags[0]["issue"] == "none_selected"
    assert "raw_payload" in payload
    assert result.raw_payload == payload["raw_payload"]


def test_extract_surfaces_extended_sections(tmp_path, monkeypatch):
    fallback_path = Path(__file__).resolve().parents[2] / "samples" / "fallback_extract.json"
    monkeypatch.setenv("AZURE_DOCINTEL_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AZURE_DOCINTEL_KEY", "key")
    monkeypatch.setenv("AZURE_DOCINTEL_MODEL_ID", "model-id")
    monkeypatch.setenv("AZURE_DOCINTEL_FALLBACK_JSON", str(fallback_path))

    pdf_path = tmp_path / "input.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock document\n")

    class DummyClient:
        def begin_analyze_document(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.uad.azure_extract._client", lambda: DummyClient())

    result = extract_1004_fields(str(pdf_path))
    assert result.payload["subject"]["public_record_owner"] == "Morgan Demo"
    assert result.payload["appraiser"]["signature_present"] is True
    photos = result.payload["photos"]
    assert photos["front_exterior"]["page_number"] == 3
    assert photos["front_exterior"]["reference"] == "https://example.com/photos/front-exterior.jpg"
    assert photos["rear_exterior"]["present"] is True
    assert photos["kitchen"]["present"] is False
    assert result.payload["reconciliation"]["appraisal_type"] == "Desktop"
    comparables = result.payload["sales_comparison"]["comparables"]
    assert comparables[0]["condition"] == "C2"
    assert result.payload["loan"]["loan_number"] == "LN-445566"
    assert result.payload["title"]["current_owner"] == "Alex Borrower"
    assert result.raw_payload["sales_comparison"]["Comparables"][0]["Identifier"] == "Comp1"
