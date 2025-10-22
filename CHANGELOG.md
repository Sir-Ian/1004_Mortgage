# Changelog

## 1.4.0 - 2024-05-11
- Normalized reconciliation appraisal types to canonical values during extraction.
- Added manual review escalation metadata to the payload schema and documentation.
- Introduced rule R-12 to flag non-"As is" appraisals unless escalated or acknowledged.

## 1.3.0 - 2024-05-10
- Added external source alignment schema support for loan documents, title, and public records.
- Introduced rule R-06 to surface cross-source mismatches with source attribution in findings.
- Documented automated integration tests validating aligned versus misaligned external data payloads.

## 1.2.0 - 2024-05-09
- Persisted borrower names from Azure extraction alongside the public-record owner in the
  canonical subject payload.
- Added refinance borrower/owner last-name alignment rule with condition severity and
  remediation guidance.

## 1.1.0 - 2024-05-08
- Added Azure photo presence and reference fields to the extraction payload and schema.
- Introduced the R-02 validation rule enforcing complete photo inventory when the report is signed.
- Exposed the validation `ruleset_version` metadata for downstream auditing.
