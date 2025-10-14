from __future__ import annotations

from typing import Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from src.api.uad import router as uad_router

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>1004 Mortgage Demo</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; background: #f5f6f8; color: #333; }
    main { max-width: 960px; margin: 0 auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; }
    form { display: flex; gap: 1rem; align-items: center; margin-bottom: 1.5rem; }
    input[type="file"] { flex: 1; }
    button { padding: 0.6rem 1.2rem; border: none; border-radius: 4px; background: #0078d4; color: #fff; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    #status { margin-bottom: 1rem; font-weight: bold; }
    pre { background: #111318; color: #e8e6e3; padding: 1rem; border-radius: 6px; overflow: auto; max-height: 480px; }
    details { margin-bottom: 1rem; }
  </style>
</head>
<body>
  <main>
    <h1>Mortgage 1004 Document Intelligence</h1>
    <p>Select a Form 1004 PDF and send it to the Azure Document Intelligence endpoint through this service.</p>
    <form id="upload-form">
      <input type="file" id="file" accept=".pdf,application/pdf" required>
      <button type="submit">Analyze document</button>
    </form>
    <div id="status">Waiting for upload.</div>
    <details open>
      <summary>Validation summary</summary>
      <pre id="summary-output">{}</pre>
    </details>
    <details>
      <summary>Raw fields from Document Intelligence</summary>
      <pre id="raw-output">{}</pre>
    </details>
  </main>
  <script>
    const form = document.getElementById("upload-form");
    const statusEl = document.getElementById("status");
    const summaryEl = document.getElementById("summary-output");
    const rawEl = document.getElementById("raw-output");

    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fileInput = document.getElementById("file");
      if (!fileInput.files.length) {
        statusEl.textContent = "Choose a PDF document before submitting.";
        return;
      }

      const submitButton = form.querySelector("button");
      submitButton.disabled = true;
      statusEl.textContent = "Uploading to Azure Document Intelligence...";
      summaryEl.textContent = "";
      rawEl.textContent = "";

      const formData = new FormData();
      formData.append("file", fileInput.files[0]);

      try {
        const response = await fetch("/uad/validate", {
          method: "POST",
          body: formData
        });
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const data = await response.json();
        statusEl.textContent = data.fallback_used
          ? "Served fallback payload (Azure call failed upstream)."
          : `Document processed (validation status: ${data.status}).`;

        const summary = {
          status: data.status,
          fallback_used: data.fallback_used,
          missing_fields: data.missing_fields,
          low_confidence_fields: data.low_confidence_fields,
          findings: data.findings,
          model_id: data.model_id
        };
        summaryEl.textContent = pretty(summary);

        rawEl.textContent = pretty(data.raw_fields);
      } catch (error) {
        statusEl.textContent = `Error: ${error.message}`;
      } finally {
        submitButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""

app = FastAPI(title="1004 Mortgage UAD Service")
app.include_router(uad_router)


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def index() -> HTMLResponse:
    return HTMLResponse(content=INDEX_HTML)


@app.get("/health", tags=["meta"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}
