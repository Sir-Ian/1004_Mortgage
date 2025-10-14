from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(autouse=True)
def _set_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_DOCINTEL_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AZURE_DOCINTEL_KEY", "key")
    monkeypatch.setenv("AZURE_DOCINTEL_MODEL_ID", "test-model")

    fallback_payload = {
        "payload": {
            "subject": {
                "address": {"street": "10 Demo St", "city": "Denver", "state": "CO", "zip": "80014"}
            },
            "contract": {"assignment_type": "Purchase"},
        },
        "raw_fields": {
            "Subject.PropertyAddress.street": {
                "type": "string",
                "value": "10 Demo St",
                "content": "10 Demo St",
                "confidence": 0.95,
                "leaf": True,
            }
        },
        "missing_fields": [],
        "low_confidence_fields": [],
        "model_id": "fallback-ui-test",
        "fallback_used": True,
    }
    fallback_path = tmp_path / "fallback_ui.json"
    fallback_path.write_text(json.dumps(fallback_payload), encoding="utf-8")
    monkeypatch.setenv("AZURE_DOCINTEL_FALLBACK_JSON", str(fallback_path))

    class DummyClient:
        def begin_analyze_document(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.uad.azure_extract._client", lambda: DummyClient())


def test_index_route_serves_html():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Mortgage 1004 Document Intelligence" in response.text


def test_validate_endpoint_returns_fallback(tmp_path):
    client = TestClient(app)
    pdf_path = tmp_path / "document.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\\n% fallback demo\\n")
    with pdf_path.open("rb") as handle:
        files = {"file": ("document.pdf", handle, "application/pdf")}
        response = client.post("/uad/validate", files=files)
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_used"] is True
    assert payload["payload"]["contract"]["assignment_type"] == "Purchase"
    assert "Subject.PropertyAddress.street" in payload["raw_fields"]
