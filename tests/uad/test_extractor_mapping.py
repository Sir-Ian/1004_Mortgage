from __future__ import annotations

from datetime import date as dt_date

from azure.ai.documentintelligence.models import AddressValue, CurrencyValue, DocumentField

from src.uad.azure_extract import (
    _addr_split,
    _bool_from_field,
    _date_mmddyyyy,
    _hoa_freq,
    _money_to_int,
    _pick_selected_label,
)


def test_mapper_shapes_payload_keys():
    assert _hoa_freq("per month") == "PerMonth"
    assert _hoa_freq("per year") == "PerYear"
    assert _hoa_freq(None) == "None"


def test_addr_split_from_address_value():
    addr = AddressValue(
        street_address="123 Pike St",
        city="Seattle",
        state="WA",
        postal_code="98101",
    )
    field = DocumentField(type="address", value_address=addr)
    assert _addr_split(field) == {
        "street": "123 Pike St",
        "city": "Seattle",
        "state": "WA",
        "zip": "98101",
    }


def test_pick_selected_label_with_alias():
    field = DocumentField(
        type="selectionGroup",
        value_selection_group=["Purchase Transaction"],
    )
    assert _pick_selected_label(field, {"Purchase Transaction": "Purchase"}) == "Purchase"


def test_money_to_int_prefers_currency_amount():
    currency = CurrencyValue(amount=123456.78, currency_code="USD", currency_symbol="$")
    field = DocumentField(type="currency", value_currency=currency)
    assert _money_to_int(field) == 123457


def test_date_mmddyyyy_from_date():
    field = DocumentField(type="date", value_date=dt_date(2024, 4, 15))
    assert _date_mmddyyyy(field) == "04/15/2024"


def test_bool_from_field_handles_yes_string():
    field = DocumentField(type="string", value_string="Yes")
    assert _bool_from_field(field) is True
