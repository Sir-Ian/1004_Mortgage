from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..uad.azure_extract import ExtractionResult, extract_1004_fields
from ..uad.validator import validate

router = APIRouter(prefix="/uad", tags=["uad"])


def _fallback_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.getenv("AZURE_DOCINTEL_FALLBACK_JSON")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).resolve().parents[2] / "samples" / "fallback_extract.json")
    return candidates


def _load_fallback_snapshot() -> dict[str, Any]:
    for candidate in _fallback_candidates():
        if candidate and candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                return cast(dict[str, Any], json.load(handle))
    raise HTTPException(status_code=404, detail="Fallback sample not available")


@router.post("/validate")
async def uad_validate(file: UploadFile = File(...)):  # noqa: B008
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Upload a PDF")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        extraction: ExtractionResult = extract_1004_fields(path)
        validation = validate(
            extraction.payload,
            "schema/uad_1004_v1.json",
            "registry/fields.json",
        )
        return {
            "payload": extraction.payload,
            "raw_payload": extraction.raw_payload,
            "raw_fields": extraction.raw_fields,
            "missing_fields": extraction.missing_fields,
            "low_confidence_fields": extraction.low_confidence_fields,
            "business_flags": extraction.business_flags,
            "model_id": extraction.model_id,
            "fallback_used": extraction.fallback_used,
            **validation,
        }
    finally:
        os.unlink(path)


@router.get("/demo")
async def uad_demo() -> dict[str, object]:
    snapshot = _load_fallback_snapshot()
    payload_obj = snapshot.get("payload")
    if isinstance(payload_obj, dict):
        payload = payload_obj
    else:
        payload = {
            "subject": cast(dict[str, Any], snapshot.get("subject", {})),
            "contract": cast(dict[str, Any], snapshot.get("contract", {})),
            "appraiser": cast(dict[str, Any], snapshot.get("appraiser", {})),
        }
    validation = validate(
        payload,
        "schema/uad_1004_v1.json",
        "registry/fields.json",
    )
    return {
        "payload": payload,
        "raw_payload": snapshot.get("raw_payload", {}),
        "raw_fields": snapshot.get("raw_fields", {}),
        "missing_fields": snapshot.get("missing_fields", []),
        "low_confidence_fields": snapshot.get("low_confidence_fields", []),
        "business_flags": snapshot.get("business_flags", []),
        "model_id": snapshot.get("model_id", "demo-fallback"),
        "fallback_used": snapshot.get("fallback_used", True),
        **validation,
    }
