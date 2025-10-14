from __future__ import annotations

import json

import pytest

from src.uad.azure_extract import ExtractionResult, extract_1004_fields


@pytest.mark.parametrize("fallback_env", [True, False])
def test_extract_uses_fallback_when_azure_fails(tmp_path, monkeypatch, fallback_env):
    payload = {
        "payload": {
            "subject": {
                "address": {"street": "100 Test St", "city": "Austin", "state": "TX", "zip": "78701"},
                "pud_indicator": False,
            },
            "contract": {"assignment_type": "Purchase"},
        },
        "raw_fields": {
            "Subject.PropertyAddress.street": {
                "type": "string",
                "value": "100 Test St",
                "content": "100 Test St",
                "confidence": 0.93,
                "leaf": True,
            }
        },
        "missing_fields": [],
        "low_confidence_fields": [],
        "model_id": "fallback-test",
        "fallback_used": True,
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
