from __future__ import annotations

from src.uad.azure_extract import _hoa_freq


def test_mapper_shapes_payload_keys():
    assert _hoa_freq("per month") == "PerMonth"
    assert _hoa_freq("per year") == "PerYear"
    assert _hoa_freq(None) == "None"
