from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AddressValue,
    AnalyzedDocument,
    CurrencyValue,
    DocumentField,
)
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK = Path(__file__).resolve().parents[2] / "samples" / "fallback_extract.json"
NONE_SELECTED_MESSAGE = "Azure Document Intelligence returned '(None Selected)' for this field."


@dataclass
class ExtractionResult:
    payload: dict[str, Any]
    raw_fields: dict[str, dict[str, Any]]
    missing_fields: list[str]
    low_confidence_fields: list[str]
    business_flags: list[dict[str, Any]]
    model_id: str
    fallback_used: bool = False


def _client() -> DocumentIntelligenceClient:
    endpoint = os.environ["AZURE_DOCINTEL_ENDPOINT"]
    key = os.environ["AZURE_DOCINTEL_KEY"]
    return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))


def _low_conf_threshold() -> float:
    try:
        return float(os.getenv("AZURE_DOCINTEL_LOW_CONFIDENCE", "0.8"))
    except ValueError:
        return 0.8


def _fallback_path() -> Path | None:
    path = os.getenv("AZURE_DOCINTEL_FALLBACK_JSON")
    if path:
        return Path(path)
    if DEFAULT_FALLBACK.exists():
        return DEFAULT_FALLBACK
    return None


def _load_fallback(model_id: str | None = None) -> ExtractionResult:
    fallback = _fallback_path()
    if not fallback or not fallback.exists():
        raise RuntimeError(
            "Azure Document Intelligence call failed and no fallback payload is available."
        )
    with fallback.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    payload = data.get("payload")
    if payload is None:
        payload = {
            "subject": data.get("subject", {}),
            "contract": data.get("contract", {}),
        }
    raw_fields = data.get("raw_fields", {})
    missing_fields = data.get("missing_fields", [])
    low_confidence_fields = data.get("low_confidence_fields", [])
    business_flags = data.get("business_flags", [])
    fallback_model = data.get("model_id")
    if isinstance(fallback_model, str) and fallback_model:
        resolved_model = fallback_model
    elif isinstance(model_id, str) and model_id:
        resolved_model = model_id
    else:
        resolved_model = os.environ.get("AZURE_DOCINTEL_MODEL_ID", "prebuilt-mortgage.us.1004")
    fallback_used = bool(data.get("fallback_used", True))
    return ExtractionResult(
        payload=payload,
        raw_fields=raw_fields,
        missing_fields=missing_fields,
        low_confidence_fields=low_confidence_fields,
        business_flags=business_flags,
        model_id=resolved_model,
        fallback_used=fallback_used,
    )


def _field_by_path(doc: AnalyzedDocument, path: str) -> DocumentField | None:
    current: DocumentField | None
    parts = path.split(".")
    fields = getattr(doc, "fields", None) or {}
    if not fields:
        return None
    current = fields.get(parts[0])
    for part in parts[1:]:
        if current is None:
            return None
        obj = current.value_object
        if not obj:
            return None
        current = obj.get(part)
    return current


def _field_text(field: DocumentField | None) -> str | None:
    if field is None:
        return None
    value = field.value_string
    if value is not None:
        stripped = value.strip()
        return stripped or None
    if field.content:
        stripped = field.content.strip()
        return stripped or None
    return None


def _addr_split(field: DocumentField | None) -> dict[str, Any]:
    addr: AddressValue | None = None
    if field is None:
        return {}
    if field.value_address:
        addr = field.value_address
    elif field.value_object:
        obj = field.value_object
        street_field = obj.get("streetAddress") or obj.get("street")
        city_field = obj.get("city")
        state_field = obj.get("state")
        zip_field = obj.get("postalCode")
        parts = {
            "street": _field_text(street_field),
            "city": _field_text(city_field),
            "state": _field_text(state_field),
            "zip": _field_text(zip_field),
        }
        return {k: v for k, v in parts.items() if v not in (None, "")}
    if not addr:
        return {}

    def s(v: str | None) -> str | None:
        return None if v is None else v.strip() or None

    parts = {
        "street": s(addr.street_address or addr.house or addr.road),
        "city": s(addr.city),
        "state": s(addr.state),
        "zip": s(addr.postal_code),
    }
    return {k: v for k, v in parts.items() if v not in (None, "")}


def _pick_selected_label(
    field: DocumentField | None, aliases: dict[str, str] | None = None
) -> str | None:
    if field is None:
        return None
    options: Iterable[str] = field.value_selection_group or []
    for option in options:
        label = str(option).strip()
        if not label:
            continue
        if aliases and label in aliases:
            return aliases[label]
        return label
    content = _field_text(field)
    if content is None:
        return None
    label = content.strip()
    if not label:
        return None
    if aliases and label in aliases:
        return aliases[label]
    return label


def _money_to_int(field: DocumentField | None) -> int | None:
    if field is None:
        return None
    currency: CurrencyValue | None = field.value_currency
    if currency and currency.amount is not None:
        return int(round(float(currency.amount)))
    if field.value_number is not None:
        return int(round(field.value_number))
    if field.value_integer is not None:
        return int(field.value_integer)
    text = _field_text(field)
    if text is None:
        return None
    try:
        return int(round(float(text.replace(",", "").replace("$", ""))))
    except Exception:
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else None


def _phone_from_field(field: DocumentField | None) -> str | None:
    if field is None:
        return None
    phone_number = getattr(field, "value_phone_number", None)
    if phone_number is not None:
        text = str(phone_number)
    else:
        content = _field_text(field)
        if content is None:
            return None
        text = content
    if not text:
        return None
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    if not digits:
        return None
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    return digits


def _date_mmddyyyy(field: DocumentField | None) -> str | None:
    if field is None:
        return None
    value: date | None = field.value_date
    if value is not None:
        return value.strftime("%m/%d/%Y")
    text = _field_text(field)
    if not text:
        return None
    s = text.strip().replace("-", "/").replace(".", "/")
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if not m:
        return None
    mm, dd, yy = m.groups()
    if len(yy) == 2:
        yy = "20" + yy
    return f"{int(mm):02d}/{int(dd):02d}/{int(yy):04d}"


def _bool_from_field(field: DocumentField | None) -> bool | None:
    if field is None:
        return None
    if field.value_boolean is not None:
        return bool(field.value_boolean)
    label = _pick_selected_label(field)
    if label is None:
        label = _field_text(field)
    if label is None:
        return None
    lowered = label.strip().lower()
    if lowered in {"yes", "y", "true"}:
        return True
    if lowered in {"no", "n", "false"}:
        return False
    return None


def _hoa_freq(label: str | None) -> str:
    if not label:
        return "None"
    t = label.lower()
    if "month" in t:
        return "PerMonth"
    if "year" in t:
        return "PerYear"
    return "None"


def _dom(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return "Unk" if s.lower().startswith("unk") else "".join(ch for ch in s if ch.isdigit()) or None


def _normalize_field_value(field: DocumentField | None) -> Any:
    if field is None:
        return None
    if field.value_string is not None:
        return field.value_string.strip() or None
    if field.value_integer is not None:
        return int(field.value_integer)
    if field.value_number is not None:
        return float(field.value_number)
    if field.value_boolean is not None:
        return bool(field.value_boolean)
    if field.value_date is not None:
        value_date: date = field.value_date
        return value_date.isoformat()
    if field.value_time is not None:
        value_time: time = field.value_time
        return value_time.isoformat()
    if field.value_currency is not None:
        currency = field.value_currency
        amount = currency.amount
        return {
            "amount": float(amount) if amount is not None else None,
            "currency_code": currency.currency_code,
        }
    if field.value_address is not None:
        return _addr_split(field)
    selection_group = field.value_selection_group
    if selection_group:
        return [str(option).strip() for option in selection_group if str(option).strip()]
    if field.value_object:
        return {k: _normalize_field_value(v) for k, v in field.value_object.items()}
    value_list = getattr(field, "value_list", None)
    if value_list:
        return [_normalize_field_value(v) for v in value_list]
    if field.content:
        return field.content.strip() or None
    return None


def _flatten_field(field: DocumentField, prefix: str) -> dict[str, dict[str, Any]]:
    value_list = getattr(field, "value_list", None)
    is_container = bool(field.value_object or value_list)
    info = {
        "type": getattr(field, "type", None),
        "value": _normalize_field_value(field),
        "content": _field_text(field),
        "confidence": float(field.confidence) if field.confidence is not None else None,
        "leaf": not is_container,
    }
    flattened: dict[str, dict[str, Any]] = {prefix: info}
    if field.value_object:
        for key, child in field.value_object.items():
            flattened.update(_flatten_field(child, f"{prefix}.{key}"))
    if value_list:
        for idx, child in enumerate(value_list):
            flattened.update(_flatten_field(child, f"{prefix}[{idx}]"))
    return flattened


def _flatten_document_fields(doc: AnalyzedDocument | None) -> dict[str, dict[str, Any]]:
    if doc is None:
        return {}
    flattened: dict[str, dict[str, Any]] = {}
    for name, field in (getattr(doc, "fields", None) or {}).items():
        flattened.update(_flatten_field(field, name))
    return flattened


def _value_is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return True
        return stripped.lower() == "(none selected)"
    if isinstance(value, list | tuple | set):
        return all(_value_is_missing(v) for v in value)
    if isinstance(value, dict):
        return all(_value_is_missing(v) for v in value.values())
    return False


def _build_business_flags(raw_fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    # Central place for underwriting/business heuristics that are more opinionated than
    # simple missing/low-confidence detection.
    for name, info in raw_fields.items():
        if not info.get("leaf"):
            continue
        value = info.get("value")
        content = info.get("content")
        values_to_check: list[str] = []
        if isinstance(value, str):
            values_to_check.append(value)
        elif isinstance(value, list | tuple | set):
            values_to_check.extend(str(item) for item in value)
        if isinstance(content, str):
            values_to_check.append(content)
        for candidate in values_to_check:
            if candidate.strip().lower() == "(none selected)":
                flags.append(
                    {
                        "field": name,
                        "issue": "none_selected",
                        "message": NONE_SELECTED_MESSAGE,
                    }
                )
                break
    return flags


def extract_1004_fields(pdf_path: str, model_id: str | None = None) -> ExtractionResult:
    default_model = os.environ.get("AZURE_DOCINTEL_MODEL_ID", "prebuilt-mortgage.us.1004")
    mid: str = model_id if model_id is not None else default_model
    try:
        client = _client()
        with open(pdf_path, "rb") as f:
            poller = client.begin_analyze_document(model_id=mid, body=f)
        result = poller.result()
    except Exception as exc:  # pragma: no cover - branches driven by runtime failures
        logger.warning("Azure Document Intelligence call failed, loading fallback payload: %s", exc)
        return _load_fallback(mid)

    documents = getattr(result, "documents", None) or []
    doc: Any = documents[0] if documents else None
    if not doc:
        return ExtractionResult(
            payload={"subject": {}, "contract": {}, "appraiser": {}},
            raw_fields={},
            missing_fields=[],
            low_confidence_fields=[],
            business_flags=[],
            model_id=mid,
        )

    # Subject.PropertyAddress is an address object
    subj_addr_field = _field_by_path(doc, "Subject.PropertyAddress")
    addr = _addr_split(subj_addr_field)

    assign_alias = {
        "Purchase Transaction": "Purchase",
        "Refinance Transaction": "Refinance",
        "Other": "Other",
    }

    subject = {
        "address": addr,
        "county": None,
        "parcel_number": _field_text(_field_by_path(doc, "Subject.AssessorParcelNumber")),
        "pud_indicator": _bool_from_field(_field_by_path(doc, "Subject.IsPud")),
        "hoa_amount": _money_to_int(_field_by_path(doc, "Subject.HoaAmount")),
        "hoa_frequency": _hoa_freq(
            _pick_selected_label(_field_by_path(doc, "Subject.HoaPaymentInterval"))
        ),
        "tax_year": _field_text(_field_by_path(doc, "Subject.TaxYear")),
        "real_estate_taxes": _money_to_int(_field_by_path(doc, "Subject.RealEstateTaxes")),
    }

    contract = {
        "assignment_type": _pick_selected_label(
            _field_by_path(doc, "Subject.AssignmentType"), assign_alias
        ),
        "contract_price": _money_to_int(_field_by_path(doc, "Contract.ContractPrice")),
        "contract_date": _date_mmddyyyy(_field_by_path(doc, "Contract.ContractDate")),
        "seller_owner_public_record": _pick_selected_label(
            _field_by_path(doc, "Contract.IsPropertySellerOwnerOfPublicRecord"),
            {"Yes": "Yes", "No": "No"},
        ),
        "financial_assistance_flag": None,
        "financial_assistance_amount": None,
        "offered_for_sale_flag": None,
        "dom": None,
        "offering_price": None,
        "offering_date": None,
        "offering_data_source": None,
    }

    appraiser_address = _addr_split(_field_by_path(doc, "Appraiser.CompanyAddress"))
    appraiser_property_address = _addr_split(
        _field_by_path(doc, "Appraiser.PropertyAppraisedAddress")
    )
    subject_status_field = _field_by_path(doc, "Appraiser.SubjectPropertyStatus")
    comparable_status_field = _field_by_path(doc, "Appraiser.ComparableSalesStatus")
    subject_status = None
    if subject_status_field and subject_status_field.value_selection_group:
        subject_status = [
            str(option).strip()
            for option in subject_status_field.value_selection_group
            if str(option).strip()
        ]
    comparable_status = None
    if comparable_status_field and comparable_status_field.value_selection_group:
        comparable_status = [
            str(option).strip()
            for option in comparable_status_field.value_selection_group
            if str(option).strip()
        ]
    appraiser = {
        "name": _field_text(_field_by_path(doc, "Appraiser.AppraiserName")),
        "company_name": _field_text(_field_by_path(doc, "Appraiser.CompanyName")),
        "company_address": appraiser_address,
        "email": _field_text(_field_by_path(doc, "Appraiser.EmailAddress")),
        "phone": _phone_from_field(_field_by_path(doc, "Appraiser.TelephoneNumber")),
        "appraised_value": _money_to_int(
            _field_by_path(doc, "Appraiser.AppraisedValueOfSubjectProperty")
        ),
        "effective_date": _date_mmddyyyy(_field_by_path(doc, "Appraiser.EffectiveDate")),
        "signature_date": _date_mmddyyyy(_field_by_path(doc, "Appraiser.SignatureAndReportDate")),
        "subject_property_status": subject_status,
        "comparable_sales_status": comparable_status,
        "property_appraised_address": appraiser_property_address,
    }

    def prune(obj: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                pruned = prune(value)
                if pruned:
                    cleaned[key] = pruned
                continue
            if isinstance(value, list):
                pruned_list = [item for item in value if item not in (None, "", [])]
                if pruned_list:
                    cleaned[key] = pruned_list
                continue
            if value in (None, "", []):
                continue
            cleaned[key] = value
        return cleaned

    payload = {
        "subject": prune(subject),
        "contract": prune(contract),
        "appraiser": prune(appraiser),
    }

    raw_fields = _flatten_document_fields(doc)
    threshold = _low_conf_threshold()
    missing_fields = sorted(
        name
        for name, info in raw_fields.items()
        if info.get("leaf")
        and _value_is_missing(info.get("value"))
        and _value_is_missing(info.get("content"))
    )
    low_confidence_fields = sorted(
        name
        for name, info in raw_fields.items()
        if info.get("leaf")
        and info.get("confidence") is not None
        and info["confidence"] < threshold
    )

    business_flags = _build_business_flags(raw_fields)

    return ExtractionResult(
        payload=payload,
        raw_fields=raw_fields,
        missing_fields=missing_fields,
        low_confidence_fields=low_confidence_fields,
        business_flags=business_flags,
        model_id=mid,
    )
