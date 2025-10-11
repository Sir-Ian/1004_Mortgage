# 1004 Mortgage UAD Service

This service extracts Uniform Residential Appraisal Report (URAR, Form 1004) data using
Azure Document Intelligence and validates the payload against Uniform Appraisal Dataset
(UAD) rules.

## Configuration

Populate a `.env` file (or export variables) based on `.env.example`.

| Variable | Description |
| --- | --- |
| `AZURE_DOCINTEL_ENDPOINT` | Azure Document Intelligence endpoint URL. |
| `AZURE_DOCINTEL_KEY` | API key for the Azure Document Intelligence resource. |
| `AZURE_DOCINTEL_MODEL_ID` | Model ID to invoke (defaults to `prebuilt-mortgage.us.1004`). |
| `HOST` | FastAPI host binding (default `0.0.0.0`). |
| `PORT` | FastAPI port (default `8000`). |

Install dependencies with:

```bash
make install
```

## Running locally

```bash
make run
```

Then submit a 1004 PDF to the validator endpoint:

```bash
curl -F "file=@samples/1004_sample.pdf" http://localhost:8000/uad/validate | jq
```

The response includes the canonical payload plus UAD findings:

```json
{
  "payload": { ... },
  "status": "fail",
  "findings": [
    {"field": "contract.contract_price", "message": "Field 'contract.contract_price' is required", "severity": "error", "rule": "uad_requirement"},
    {"field": "X002", "message": "PUD implies HOA freq known", "severity": "warn", "rule": "X002"}
  ]
}
```

> **Note:** The extractor relies on the Azure prebuilt `prebuilt-mortgage.us.1004` model. No
> document contents or secrets are logged.

## Development

```bash
make lint
make test
```

- `make lint` runs Ruff, Black, and MyPy.
- `make test` runs the pytest suite.

## API Surface

- `POST /uad/validate`: Accepts a PDF upload, extracts subject and contract data,
  validates against `schema/uad_1004_v1.json` and `registry/fields.json`, and returns
  canonical data plus validation findings.
- `GET /health`: Simple health probe.

The validator enforces JSON Schema constraints, field-level requirements, and
cross-field rules defined in `registry/fields.json`.
