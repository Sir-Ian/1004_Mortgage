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


@dataclass
class ExtractionResult:
    payload: dict[str, Any]
    raw_fields: dict[str, dict[str, Any]]
    missing_fields: list[str]
    low_confidence_fields: list[str]
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
        raise RuntimeError("Azure Document Intelligence call failed and no fallback payload is available.")
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
    resolved_model = data.get("model_id") or model_id or os.environ.get(
        "AZURE_DOCINTEL_MODEL_ID", "prebuilt-mortgage.us.1004"
    )
    fallback_used = bool(data.get("fallback_used", True))
    return ExtractionResult(
        payload=payload,
        raw_fields=raw_fields,
        missing_fields=missing_fields,
        low_confidence_fields=low_confidence_fields,
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
    if field.value_selection_group:
        return [str(option).strip() for option in field.value_selection_group if str(option).strip()]
    if field.value_object:
        return {k: _normalize_field_value(v) for k, v in field.value_object.items()}
    if field.value_list:
        return [_normalize_field_value(v) for v in field.value_list]
    if field.content:
        return field.content.strip() or None
    return None


def _flatten_field(field: DocumentField, prefix: str) -> dict[str, dict[str, Any]]:
    is_container = bool(field.value_object or field.value_list)
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
    if field.value_list:
        for idx, child in enumerate(field.value_list):
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
        return value.strip() == ""
    if isinstance(value, (list, tuple, set)):
        return all(_value_is_missing(v) for v in value)
    if isinstance(value, dict):
        return all(_value_is_missing(v) for v in value.values())
    return False


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
            payload={"subject": {}, "contract": {}},
            raw_fields={},
            missing_fields=[],
            low_confidence_fields=[],
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

    def prune(obj: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in obj.items() if v not in (None, "", [])}

    payload = {"subject": prune(subject), "contract": prune(contract)}

    raw_fields = _flatten_document_fields(doc)
    threshold = _low_conf_threshold()
    missing_fields = sorted(
        name
        for name, info in raw_fields.items()
        if info.get("leaf") and _value_is_missing(info.get("value")) and _value_is_missing(info.get("content"))
    )
    low_confidence_fields = sorted(
        name
        for name, info in raw_fields.items()
        if info.get("leaf")
        and info.get("confidence") is not None
        and info["confidence"] < threshold
    )

    return ExtractionResult(
        payload=payload,
        raw_fields=raw_fields,
        missing_fields=missing_fields,
        low_confidence_fields=low_confidence_fields,
        model_id=mid,
    )
