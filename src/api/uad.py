from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..uad.azure_extract import extract_1004_fields
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
        payload = extract_1004_fields(path)
        result = validate(payload, "schema/uad_1004_v1.json", "registry/fields.json")
        return {"payload": payload, **result}
    finally:
        os.unlink(path)
