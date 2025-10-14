from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..uad.azure_extract import ExtractionResult, extract_1004_fields
from ..uad.validator import validate

router = APIRouter(prefix="/uad", tags=["uad"])


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
