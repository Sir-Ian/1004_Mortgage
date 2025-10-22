from src.uad.azure_extract import _normalize_appraisal_type


def test_normalize_appraisal_type_as_is_variants() -> None:
    assert _normalize_appraisal_type("AS IS") == "As is"
    assert _normalize_appraisal_type("as-is") == "As is"
    assert _normalize_appraisal_type(" As Is Condition ") == "As is"


def test_normalize_appraisal_type_subject_to_variants() -> None:
    assert _normalize_appraisal_type("Subject To") == "Subject to"
    assert _normalize_appraisal_type("subject to completion per plans and specs") == "Subject to"


def test_normalize_appraisal_type_passthrough() -> None:
    assert _normalize_appraisal_type("Desktop") == "Desktop"
    assert _normalize_appraisal_type(None) is None
