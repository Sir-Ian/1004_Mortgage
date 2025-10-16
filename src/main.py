from __future__ import annotations

from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from src.api.uad import router as uad_router

app = FastAPI(title="1004 Mortgage UAD Service")
app.include_router(uad_router)

_FRONTEND_PATH = Path(__file__).resolve().parents[1] / "form-1004-analysis-liquidglass.html"


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def index() -> HTMLResponse:
    if not _FRONTEND_PATH.exists():
        raise HTTPException(status_code=500, detail="Frontend bundle is missing.")
    return HTMLResponse(content=_FRONTEND_PATH.read_text(encoding="utf-8"))


@app.get("/health", tags=["meta"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}
