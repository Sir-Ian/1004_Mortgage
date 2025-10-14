from __future__ import annotations

import os
import re
from collections.abc import Iterable
from datetime import date
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AddressValue,
    AnalyzedDocument,
    CurrencyValue,
    DocumentField,
)
from azure.core.credentials import AzureKeyCredential


def _client() -> DocumentIntelligenceClient:
    endpoint = os.environ["AZURE_DOCINTEL_ENDPOINT"]
    key = os.environ["AZURE_DOCINTEL_KEY"]
    return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))


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


def extract_1004_fields(pdf_path: str, model_id: str | None = None) -> dict[str, Any]:
    client = _client()
    default_model = os.environ.get("AZURE_DOCINTEL_MODEL_ID", "prebuilt-mortgage.us.1004")
    mid: str = model_id if model_id is not None else default_model
    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document(model_id=mid, body=f)
    result = poller.result()

    # Gather fields (single document expected)
    documents = getattr(result, "documents", None) or []
    doc: Any = documents[0] if documents else None
    if not doc:
        return {"subject": {}, "contract": {}}

    # Subject.PropertyAddress is an address object
    subj_addr_field = _field_by_path(doc, "Subject.PropertyAddress")
    addr = _addr_split(subj_addr_field)

    # Selection aliases for enums we normalize
    assign_alias = {
        "Purchase Transaction": "Purchase",
        "Refinance Transaction": "Refinance",
        "Other": "Other",
    }

    # Map Azure → canonical
    subject = {
        "address": addr,
        "county": None,  # not in the prebuilt list; may derive later
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
        # Financial assistance fields not in prebuilt list; leave None for now
        "financial_assistance_flag": None,
        "financial_assistance_amount": None,
        "offered_for_sale_flag": None,
        "dom": None,
        "offering_price": None,
        "offering_date": None,
        "offering_data_source": None,
    }

    # Prune empty keys
    def prune(obj: dict) -> dict:
        return {k: v for k, v in obj.items() if v not in (None, "", [])}

    return {"subject": prune(subject), "contract": prune(contract)}
