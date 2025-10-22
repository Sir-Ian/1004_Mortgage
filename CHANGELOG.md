# Changelog

## 1.2.0 - 2024-05-09
- Persisted borrower names from Azure extraction alongside the public-record owner in the
  canonical subject payload.
- Added refinance borrower/owner last-name alignment rule with condition severity and
  remediation guidance.

## 1.1.0 - 2024-05-08
- Added Azure photo presence and reference fields to the extraction payload and schema.
- Introduced the R-02 validation rule enforcing complete photo inventory when the report is signed.
- Exposed the validation `ruleset_version` metadata for downstream auditing.
