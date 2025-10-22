from __future__ import annotations

from io import BytesIO
from typing import Any, TypeAlias

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.uad.azure_extract import ExtractionResult

from .builders import base_payload, signed_report_payload

ClientWithStub: TypeAlias = tuple[TestClient, dict[str, ExtractionResult]]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> ClientWithStub:
    result_holder: dict[str, ExtractionResult] = {}

    def _fake_extract(_: str) -> ExtractionResult:
        if "result" not in result_holder:
            raise AssertionError("Test must set result_holder['result'] before calling endpoint")
        return result_holder["result"]

    monkeypatch.setattr("src.api.uad.extract_1004_fields", _fake_extract)
    return TestClient(app), result_holder


def _make_result(payload: dict[str, Any], *, fallback_used: bool = False) -> ExtractionResult:
    return ExtractionResult(
        payload=payload,
        raw_payload={},
        raw_fields={},
        missing_fields=[],
        low_confidence_fields=[],
        business_flags=[],
        model_id="unit-test-model",
        fallback_used=fallback_used,
    )


def _post_pdf(client: TestClient) -> dict[str, Any]:
    file = BytesIO(b"%PDF-1.4\n% integration test payload\n")
    file.seek(0)
    response = client.post(
        "/uad/validate",
        files={"file": ("report.pdf", file, "application/pdf")},
    )
    assert response.status_code == 200
    return response.json()


def test_validate_endpoint_reports_rule_hits(client: ClientWithStub) -> None:
    client_app, holder = client
    failing_payload = base_payload()
    failing_payload["contract"].pop("contract_price")
    holder["result"] = _make_result(failing_payload)

    payload = _post_pdf(client_app)

    assert payload["status"] == "fail"
    requirement_findings = [f for f in payload["findings"] if f["rule"] == "uad_requirement"]
    assert requirement_findings
    assert any(f["field"] == "contract.contract_price" for f in requirement_findings)


def test_validate_endpoint_reports_pass_snapshot(client: ClientWithStub) -> None:
    client_app, holder = client
    holder["result"] = _make_result(signed_report_payload())

    payload = _post_pdf(client_app)

    assert payload["status"] == "pass"
    assert not [f for f in payload["findings"] if f["severity"] == "error"]
    assert payload["fallback_used"] is False
