from __future__ import annotations

import os
import re
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential


def _client() -> DocumentIntelligenceClient:
    endpoint = os.environ["AZURE_DOCINTEL_ENDPOINT"]
    key = os.environ["AZURE_DOCINTEL_KEY"]
    return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))


def _addr_split(addr: dict) -> dict[str, Any]:
    # Azure returns an address object; normalize into parts we expect.
    # Fields may be None; guard and trim.
    def s(v):
        return None if v is None else str(v).strip()

    parts = {
        "street": s(addr.get("streetAddress") or addr.get("street")),
        "city": s(addr.get("city")),
        "state": s(addr.get("state")),
        "zip": s(addr.get("postalCode")),
    }
    return {k: v for k, v in parts.items() if v not in (None, "")}


def _yesno_from_selection(sel: dict | None) -> str | None:
    # selectionGroup rendered as ':selected:' labels; DI SDK yields structured values.
    if not sel:
        return None
    # Prefer normalized text if present
    v = sel.get("value") or sel.get("content") or ""
    t = str(v).strip().lower()
    if t in ("yes", "y"):
        return "Yes"
    if t in ("no", "n"):
        return "No"
    return None


def _pick_selected_label(group: dict | None, aliases: dict[str, str] | None = None) -> str | None:
    if not group:
        return None
    # Expect one selected option; value/label can vary by SDK version
    chosen = group.get("selectedOption") or group.get("value") or group.get("content")
    if not chosen:
        return None
    label = str(chosen).strip()
    if aliases and label in aliases:
        return aliases[label]
    return label


def _int(v) -> int | None:
    if v is None:
        return None
    s = "".join(ch for ch in str(v) if ch.isdigit())
    return int(s) if s else None


def _money_to_int(v) -> int | None:
    # UAD wants whole dollars; coerce numeric/decimal to int
    if v is None:
        return None
    try:
        return int(round(float(str(v).replace(",", "").replace("$", ""))))
    except Exception:
        return _int(v)


def _date_mmddyyyy(v) -> str | None:
    if not v:
        return None
    s = str(v).strip().replace("-", "/").replace(".", "/")
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if not m:
        return None
    mm, dd, yy = m.groups()
    if len(yy) == 2:
        yy = "20" + yy
    return f"{int(mm):02d}/{int(dd):02d}/{int(yy):04d}"


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

    # Helper to read a field by dotted path in Azure model:
    def get(path: str):
        if doc is None:
            return None
        cur: Any = getattr(doc, "fields", {}) or {}
        for part in path.split("."):
            if isinstance(cur, dict):
                field = cur.get(part)
                cur = field.get("value") if isinstance(field, dict) else None
            else:
                cur = None
            if cur is None:
                break
        return cur

    # Subject.PropertyAddress is an address object
    subj_addr = get("Subject.PropertyAddress") or {}
    addr = _addr_split(subj_addr if isinstance(subj_addr, dict) else {})

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
        "parcel_number": get("Subject.AssessorParcelNumber"),
        "pud_indicator": bool(get("Subject.IsPud")) if get("Subject.IsPud") is not None else None,
        "hoa_amount": _money_to_int(get("Subject.HoaAmount")),
        "hoa_frequency": _hoa_freq(_pick_selected_label(get("Subject.HoaPaymentInterval"))),
        "tax_year": str(get("Subject.TaxYear")) if get("Subject.TaxYear") is not None else None,
        "real_estate_taxes": _money_to_int(get("Subject.RealEstateTaxes")),
    }

    contract = {
        "assignment_type": _pick_selected_label(get("Subject.AssignmentType"), assign_alias),
        "contract_price": _money_to_int(get("Contract.ContractPrice")),
        "contract_date": _date_mmddyyyy(get("Contract.ContractDate")),
        "seller_owner_public_record": _pick_selected_label(
            get("Contract.IsPropertySellerOwnerOfPublicRecord"), {"Yes": "Yes", "No": "No"}
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
