from __future__ import annotations

from fastapi import FastAPI

from src.api.uad import router as uad_router

app = FastAPI(title="1004 Mortgage UAD Service")
app.include_router(uad_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
