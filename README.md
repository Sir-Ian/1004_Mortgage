# 1004 Mortgage UAD Service

This service extracts Uniform Residential Appraisal Report (URAR, Form 1004) data using
Azure Document Intelligence and validates the payload against Uniform Appraisal Dataset
(UAD) rules. The end goal is an end-to-end workflow where business users upload
appraisal packages, Azure Document Intelligence performs OCR/extraction, and this
service renders the structured results and compliance gaps in a shareable report.

## Configuration

Populate a `.env` file (or export variables) based on `.env.example`.

| Variable | Description |
| --- | --- |
| `AZURE_DOCINTEL_ENDPOINT` | Azure Document Intelligence endpoint URL. |
| `AZURE_DOCINTEL_KEY` | API key for the Azure Document Intelligence resource. |
| `AZURE_DOCINTEL_MODEL_ID` | Model ID to invoke (defaults to `prebuilt-mortgage.us.1004`). |
| `AZURE_DOCINTEL_FILE` | Optional default path to the input PDF for the sample runner. |
| `AZURE_DOCINTEL_FALLBACK_JSON` | Optional local JSON payload used when the Azure call fails (defaults to `samples/fallback_extract.json`). |
| `AZURE_DOCINTEL_LOW_CONFIDENCE` | Optional float threshold (default `0.8`) for flagging low-confidence fields. |
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

### Running the Azure sample script

If you want to replicate the Azure quickstart output verbatim, run the helper script that
mirrors the documentation example:

```bash
python samples/prebuilt_mortgage_1004.py --file path/to/form1004.pdf \
  --endpoint "$AZURE_DOCINTEL_ENDPOINT" --key "$AZURE_DOCINTEL_KEY"
```

The script accepts the same values via `AZURE_DOCINTEL_ENDPOINT`, `AZURE_DOCINTEL_KEY`,
`AZURE_DOCINTEL_MODEL_ID`, and `AZURE_DOCINTEL_FILE` environment variables so you can
store them in `.env` for local development.

## Browser Demo

Start the FastAPI service (`make run`) and open [http://localhost:8000/](http://localhost:8000/).
The lightweight UI lets you upload a Form 1004 PDF, forwards it to Azure Document
Intelligence, and displays:

- Validation findings against the canonical schema and UAD rule registry.
- Raw fields, types, confidence scores, missing-field heuristics, and business-rule flags.
- A banner when the local fallback payload is used because Azure is unavailable.

You can pre-populate the demo with `samples/fallback_extract.json` to run without
network connectivity or to simulate Azure outages.

## Document Intelligence Field Inventory

The Azure prebuilt `prebuilt-mortgage.us.1004` model surfaces the following fields.
This list is generated from the SDK example in `samples/prebuilt_mortgage_1004.py`
and drives the UI's raw field display so product teams can see exactly what the model
returns during the proof of concept.

```
AppraisalEffectiveDate
AppraisalType
AppraisedMarketValue
AppraisedValueOfSubjectProperty
Appraiser
AppraiserName
AssessorParcelNumber
AssignmentType
BasementArea
BasementFinish
BorrowerName
BuiltUpType
CompanyAddress
CompanyName
ComparableSalePrice1
ComparableSalePrice2
ComparableSalePrice3
ComparableSalesStatus
Contract
ContractDate
ContractPrice
DamageEvidenceType
Deficiencies
DesignStyle
EffectiveAgeInYears
EffectiveDate
EmailAddress
FemaMapDate
FemaMapNumber
FoundationType
GrowthType
HasDeficiencies
HasMultiDwellingUnits
HoaAmount
HoaPaymentInterval
Improvements
IndicatedValue
IndicatedValueByCostApproach
IndicatedValueByIncomeApproach
IndicatedValueBySalesComparisonApproach
IsBuilderInControlOfHoa
IsFemaSpecialFloodArea
IsPropertySellerOwnerOfPublicRecord
IsPud
LegalDescription
LenderOrClientAddress
LenderOrClientName
LocationType
MarketingTimeTrend
Neighborhood
OccupantType
PropertyAddress
PropertyAppraisedAddress
PropertyRightsAppraisedType
PropertyValuesTrend
PublicRecordOwner
PudInfo
RealEstateTaxes
Reconciliation
SalesComparisonApproach
SignatureAndReportDate
Site
Status
Subject
SubjectPropertyStatus
TaxYear
TelephoneNumber
Type
UnitType
UnitsType
Utilities
YearBuilt
```

Only a subset of these fields is required for the canonical payload described below.
The `raw_fields` object returned by `/uad/validate` keeps the full set (value, confidence,
and whether a fallback payload was used) so you can extend the schema as needed.

## Canonical payload coverage

`schema/uad_1004_v1.json` now includes three top-level sections:

- **subject** – Address, parcel, tax, and HOA indicators for the property under review.
- **contract** – Assignment type, pricing, and offer-level metadata.
- **appraiser** – Name, firm, contact details, appraised value, effective/signature dates,
  property-status selections, and the company/property addresses lifted directly from
  the Azure raw fields.

The `/uad/validate` response also returns:

- `missing_fields` – Flattened paths whose extracted values are empty or marked as
  `(None Selected)` by Azure.
- `low_confidence_fields` – Leaf fields with confidence below the configurable threshold.
- `business_flags` – A dedicated space for higher-level heuristics. Currently it records
  `(None Selected)` findings and is ready for additional rules as underwriting logic
  matures.

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
  canonical data (subject, contract, appraiser), raw field snapshots, business flags,
  and validation findings.
- `GET /health`: Simple health probe.

The validator enforces JSON Schema constraints, field-level requirements, and
cross-field rules defined in `registry/fields.json`.

## Recommendations

To keep improving the demo toward production readiness:

1. Replace the synthetic fallback payload with a sanitized capture from Azure once you
   have customer-provided documents (and refresh it periodically).
2. Add historical storage so multiple uploads can be compared over time and exported as
   PDF/Excel reports for stakeholders.
3. Introduce authentication and per-upload audit logs before exposing the tool broadly.
4. Expand `business_flags` with portfolio-specific underwriting rules (e.g., HOA vs. PUD
   consistency, FEMA flood-zone deltas, missing license data).
