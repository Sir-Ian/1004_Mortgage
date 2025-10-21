from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from src.api.uad import router as uad_router
from src.env_loader import load_env_file

FRONTEND_PATH = Path(__file__).resolve().parents[1] / "form-1004-analysis-liquidglass.html"

load_env_file()

app = FastAPI(title="1004 Mortgage UAD Service")
app.include_router(uad_router)


def _load_frontend() -> str:
    try:
        return FRONTEND_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Front-end asset is missing.") from exc


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def index() -> HTMLResponse:
    return HTMLResponse(content=_load_frontend())


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
