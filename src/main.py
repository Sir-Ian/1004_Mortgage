from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from src.api.uad import router as uad_router

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>1004 Mortgage Demo</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 2rem;
      background: #f5f6f8;
      color: #333;
    }
    main {
      max-width: 1024px;
      margin: 0 auto;
      background: #fff;
      padding: 2rem;
      border-radius: 8px;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    }
    h1 {
      margin-top: 0;
    }
    form {
      display: flex;
      gap: 1rem;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    input[type="file"] {
      flex: 1;
    }
    button {
      padding: 0.6rem 1.2rem;
      border: none;
      border-radius: 4px;
      background: #0078d4;
      color: #fff;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    #status {
      margin-bottom: 1.5rem;
      font-weight: bold;
    }
    pre {
      background: #111318;
      color: #e8e6e3;
      padding: 1rem;
      border-radius: 6px;
      overflow: auto;
      max-height: 480px;
    }
    details {
      margin-bottom: 1rem;
    }
    .flags {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    .flag-card {
      background: #f0f4ff;
      border-radius: 6px;
      padding: 1rem;
      border: 1px solid #c6d2f1;
    }
    .flag-card h2 {
      margin-top: 0;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .flag-list {
      list-style: none;
      padding-left: 1rem;
      margin: 0;
      max-height: 160px;
      overflow-y: auto;
    }
    .flag-list li {
      margin-bottom: 0.35rem;
      padding-left: 0.25rem;
    }
    .flag-empty {
      color: #4d5766;
      font-style: italic;
    }
    .flag-missing {
      color: #b0152c;
      font-weight: 600;
    }
    .flag-low {
      color: #b86e00;
      font-weight: 600;
    }
    .flag-business {
      color: #005a9e;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <main>
    <h1>Mortgage 1004 Document Intelligence</h1>
    <p>
      Select a Form 1004 PDF and send it to the Azure Document Intelligence endpoint
      through this service.
    </p>
    <form id="upload-form">
      <input type="file" id="file" accept=".pdf,application/pdf" required>
      <button type="submit">Analyze document</button>
    </form>
    <div id="status">Waiting for upload.</div>
    <section class="flags">
      <div class="flag-card">
        <h2>Missing fields</h2>
        <ul id="missing-list" class="flag-list"></ul>
      </div>
      <div class="flag-card">
        <h2>Low confidence</h2>
        <ul id="low-list" class="flag-list"></ul>
      </div>
      <div class="flag-card">
        <h2>Business flags</h2>
        <ul id="business-list" class="flag-list"></ul>
      </div>
    </section>
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
    const missingList = document.getElementById("missing-list");
    const lowList = document.getElementById("low-list");
    const businessList = document.getElementById("business-list");

    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    function renderList(element, items, emptyMessage, itemClass) {
      element.innerHTML = "";
      if (!items || items.length === 0) {
        const li = document.createElement("li");
        li.textContent = emptyMessage;
        li.classList.add("flag-empty");
        element.appendChild(li);
        return;
      }
      items.forEach((item) => {
        const li = document.createElement("li");
        li.textContent =
          typeof item === "string"
            ? item
            : `${item.field}: ${item.message ?? item.issue}`;
        if (itemClass) {
          li.classList.add(itemClass);
        }
        element.appendChild(li);
      });
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
      renderList(missingList, [], "No missing fields detected.", "flag-missing");
      renderList(lowList, [], "No low-confidence fields detected.", "flag-low");
      renderList(businessList, [], "No business flags raised.", "flag-business");

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
          business_flags: data.business_flags,
          findings: data.findings,
          model_id: data.model_id
        };
        summaryEl.textContent = pretty(summary);

        renderList(
          missingList,
          data.missing_fields,
          "No missing fields detected.",
          "flag-missing"
        );
        renderList(
          lowList,
          data.low_confidence_fields,
          "No low-confidence fields detected.",
          "flag-low"
        );
        renderList(
          businessList,
          data.business_flags,
          "No business flags raised.",
          "flag-business"
        );
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
async def health() -> dict[str, str]:
    return {"status": "ok"}
