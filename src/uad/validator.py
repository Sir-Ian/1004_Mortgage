from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from . import RULESET_VERSION

SIGNATURE_REQUIREMENTS_PATH = "registry/signature_requirements.json"
PHOTO_REQUIREMENTS_PATH = "registry/photo_requirements.json"


SOURCE_LABELS: dict[str, str] = {
    "uad": "UAD",
    "loan_docs": "Loan docs",
    "title": "Title",
    "public_records": "Public records",
}


@dataclass
class Finding:
    field: str
    message: str
    severity: str
    rule: str
    sources: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
            "rule": self.rule,
        }
        if self.sources is not None:
            payload["sources"] = self.sources
        return payload


class AttrDict(dict):
    """Dictionary supporting attribute access returning None when missing."""

    def __getattr__(self, item: str) -> Any:
        return self.get(item)


def _load_json(path: str | Path) -> dict[str, Any]:
    data_path = Path(path)
    if not data_path.is_absolute():
        base_dir = Path(__file__).resolve().parents[2]
        data_path = base_dir / data_path
    with data_path.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


def _to_attr(value: Any) -> Any:
    if isinstance(value, dict):
        return AttrDict({k: _to_attr(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_attr(v) for v in value]
    return value


def _normalize_expr(expr: str) -> str:
    replacements = {
        r"\btrue\b": "True",
        r"\bfalse\b": "False",
        r"\bnull\b": "None",
    }
    normalized = expr
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def _normalize_last_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    tokens = [
        token.strip(" ,.").upper() for token in re.split(r"[\s\-&]+", value) if token.strip(" ,.")
    ]
    if not tokens:
        return None
    return tokens[-1]


def _evaluate_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, context)
    if isinstance(node, ast.BoolOp):
        values = [_evaluate_node(value, context) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(v) for v in values)
        if isinstance(node.op, ast.Or):
            return any(bool(v) for v in values)
        raise ValueError("Unsupported boolean operator")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_evaluate_node(node.operand, context))
    if isinstance(node, ast.Compare):
        left = _evaluate_node(node.left, context)
        for operator, comparator in zip(node.ops, node.comparators, strict=False):
            right = _evaluate_node(comparator, context)
            if isinstance(operator, ast.Eq):
                outcome = left == right
            elif isinstance(operator, ast.NotEq):
                outcome = left != right
            elif isinstance(operator, ast.In):
                try:
                    outcome = left in right
                except TypeError:
                    outcome = False
            elif isinstance(operator, ast.NotIn):
                try:
                    outcome = left not in right
                except TypeError:
                    outcome = True
            else:
                raise ValueError("Unsupported comparison operator")
            if not outcome:
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        lowered = node.id.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "none":
            return None
        return context.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _evaluate_node(node.value, context)
        if base is None:
            return None
        if isinstance(base, dict):
            return base.get(node.attr)
        return getattr(base, node.attr, None)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_evaluate_node(element, context) for element in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_evaluate_node(element, context) for element in node.elts)
    if isinstance(node, ast.Subscript):
        base = _evaluate_node(node.value, context)
        key = _evaluate_node(node.slice, context)
        try:
            return base[key]
        except Exception:
            return None
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def _safe_eval(expr: str, context: dict[str, Any]) -> bool:
    if not expr:
        return False
    normalized = _normalize_expr(expr)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError:
        return False
    try:
        result = _evaluate_node(tree.body, context)
    except ValueError:
        return False
    return bool(result)


def _get_field(payload: dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    current: Any = payload
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list | dict):
        return len(value) == 0
    return False


def _schema_findings(payload: dict[str, Any], schema: dict[str, Any]) -> list[Finding]:
    validator = Draft202012Validator(schema)
    findings: list[Finding] = []
    for error in validator.iter_errors(payload):
        path = ".".join(str(p) for p in error.path)
        findings.append(
            Finding(
                field=path or "$",
                message=error.message,
                severity="error",
                rule="schema",
            )
        )
    return findings


def _field_requirements(
    payload: dict[str, Any], registry: dict[str, Any], context: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    for field in registry.get("fields", []):
        code = field.get("code")
        if not code:
            continue
        uad_type = field.get("uad", "Requirement")
        condition_expr = field.get("required_when")
        condition = True if uad_type == "Requirement" and not condition_expr else False
        if condition_expr:
            condition = _safe_eval(condition_expr, context)
        if not condition:
            continue
        value = _get_field(payload, code)
        if _is_missing(value):
            severity = "error" if uad_type == "Requirement" else "warn"
            findings.append(
                Finding(
                    field=code,
                    message=f"Field '{code}' is required",
                    severity=severity,
                    rule="uad_requirement",
                )
            )
    return findings


def _cross_rule_findings(
    payload: dict[str, Any], registry: dict[str, Any], context: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    for rule in registry.get("cross_rules", []):
        rule_type = rule.get("type")
        if rule_type == "refinance_owner_match":
            findings.extend(_refinance_owner_match_findings(rule, payload))
            continue
        if rule_type == "reconciliation_appraisal_type":
            findings.extend(_reconciliation_appraisal_type_findings(rule, payload))
            continue
        expr = rule.get("expr")
        if not expr:
            continue
        severity = rule.get("severity", "warn")
        rule_id = rule.get("id", "")
        desc = rule.get("desc", "")
        if "->" in expr:
            antecedent_raw, consequent_raw = expr.split("->", 1)
            antecedent = antecedent_raw.strip()
            consequent = consequent_raw.strip()
            if _safe_eval(antecedent, context) and not _safe_eval(consequent, context):
                findings.append(
                    Finding(
                        field=desc or rule_id,
                        message=desc or expr,
                        severity=severity,
                        rule=rule_id or "cross_rule",
                    )
                )
        else:
            if not _safe_eval(expr, context):
                findings.append(
                    Finding(
                        field=desc or rule_id,
                        message=desc or expr,
                        severity=severity,
                        rule=rule_id or "cross_rule",
                    )
                )
    return findings


def _extract_alignment_sources(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources_raw = payload.get("sources")
    if not isinstance(sources_raw, dict):
        return {}
    sources: dict[str, dict[str, Any]] = {}
    for name in ("loan_docs", "title", "public_records"):
        value = sources_raw.get(name)
        if isinstance(value, dict):
            sources[name] = value
    return sources


def _normalize_for_compare(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, int | float | bool):
        return value
    if value is None:
        return None
    return str(value)


def _format_alignment_message(field: str, values: dict[str, Any]) -> str:
    parts: list[str] = []
    for name, value in values.items():
        label = SOURCE_LABELS.get(name, name.replace("_", " ").title())
        display = "—" if _is_missing(value) else str(value)
        parts.append(f"{label}: {display}")
    details = "; ".join(parts)
    return f"Field '{field}' differs across sources. {details}."


def _alignment_fields(registry: dict[str, Any]) -> list[str]:
    alignment = registry.get("source_alignment")
    if isinstance(alignment, dict):
        fields = alignment.get("required_fields", [])
        return [str(field) for field in fields if isinstance(field, str)]
    return [
        str(field.get("code"))
        for field in registry.get("fields", [])
        if isinstance(field, dict) and field.get("code") and field.get("uad") == "Requirement"
    ]


def _source_alignment_findings(payload: dict[str, Any], registry: dict[str, Any]) -> list[Finding]:
    sources = _extract_alignment_sources(payload)
    if not sources:
        return []

    findings: list[Finding] = []
    for field in _alignment_fields(registry):
        values: dict[str, Any] = {"uad": _get_field(payload, field)}
        for name, source_payload in sources.items():
            values[name] = _get_field(source_payload, field)

        non_missing = {
            name: _normalize_for_compare(value)
            for name, value in values.items()
            if not _is_missing(value)
        }
        if len(non_missing) <= 1:
            continue
        unique_values = {val for val in non_missing.values()}
        if len(unique_values) <= 1:
            continue

        sources_detail = {
            name: {
                "value": None if _is_missing(value) else value,
                "missing": _is_missing(value),
            }
            for name, value in values.items()
        }
        message = _format_alignment_message(field, values)
        findings.append(
            Finding(
                field=field,
                message=message,
                severity="error",
                rule="R-06",
                sources=sources_detail,
            )
        )
    return findings


def _refinance_owner_match_findings(rule: dict[str, Any], payload: dict[str, Any]) -> list[Finding]:
    assignment_type = _get_field(payload, "contract.assignment_type")
    if assignment_type != "Refinance":
        return []
    borrower_name = _get_field(payload, "subject.borrower_name") or _get_field(
        payload, "title.current_owner"
    )
    owner_name = _get_field(payload, "subject.public_record_owner")
    borrower_last = _normalize_last_name(borrower_name)
    owner_last = _normalize_last_name(owner_name)
    if not borrower_last or not owner_last:
        return []
    if borrower_last == owner_last:
        return []
    severity = rule.get("severity", "condition")
    rule_id = rule.get("id", "cross_rule")
    desc = rule.get(
        "desc",
        "Borrower and public-record owner last names must match for refinance assignments.",
    )
    remediation = rule.get(
        "remediation",
        "Confirm title/borrower data align or document the reason for the discrepancy.",
    )
    borrower_display = borrower_name or "—"
    owner_display = owner_name or "—"
    message = (
        f"{desc} Borrower: {borrower_display}; Public record owner: {owner_display}. "
        f"{remediation}"
    )
    return [
        Finding(
            field="subject.borrower_name",
            message=message,
            severity=severity,
            rule=rule_id,
        )
    ]


def _reconciliation_appraisal_type_findings(
    rule: dict[str, Any], payload: dict[str, Any]
) -> list[Finding]:
    appraisal_type_raw = _get_field(payload, "reconciliation.appraisal_type")
    if not isinstance(appraisal_type_raw, str):
        return []
    appraisal_type = appraisal_type_raw.strip()
    if not appraisal_type:
        return []
    lowered = appraisal_type.lower()
    if lowered.startswith("as is") or lowered in {"as-is", "asis", "as is"}:
        return []

    escalated = bool(_get_field(payload, "review.escalated"))
    acknowledged = bool(_get_field(payload, "review.acknowledged"))
    if escalated or acknowledged:
        return []

    severity = rule.get("severity", "condition")
    rule_id = rule.get("id", "R-12")
    desc = rule.get(
        "desc",
        "Reports not marked 'As is' must be escalated or acknowledged by a reviewer.",
    )
    message = f"{desc} Current appraisal type: {appraisal_type}."
    return [
        Finding(
            field="reconciliation.appraisal_type",
            message=message,
            severity=severity,
            rule=rule_id,
        )
    ]


def _signature_requirement_findings(
    payload: dict[str, Any], requirements: dict[str, Any]
) -> list[Finding]:
    signature_present = _get_field(payload, "appraiser.signature_present")
    signature_date = _get_field(payload, "appraiser.signature_date")
    if not signature_present or _is_missing(signature_date):
        return []

    config = requirements.get("requirements", {}) if requirements else {}
    field_paths: list[str] = []

    for path in config.get("certifications", []):
        if isinstance(path, str):
            field_paths.append(path)

    for path in config.get("photos", []):
        if isinstance(path, str):
            field_paths.append(path)

    sections = config.get("sections", {})
    if isinstance(sections, dict):
        for key in sorted(sections):
            section_paths = sections.get(key, [])
            if isinstance(section_paths, list):
                for path in section_paths:
                    if isinstance(path, str):
                        field_paths.append(path)

    for field_path in field_paths:
        value = _get_field(payload, field_path)
        if _is_missing(value):
            message = (
                "Appraiser signature requires certifications, photo inventory, "
                "and Sections A–D to be complete before finalizing the report. "
                f"First missing field: '{field_path}'."
            )
            return [
                Finding(
                    field=field_path,
                    message=message,
                    severity="error",
                    rule="R-01",
                )
            ]
    return []


def _photo_inventory_findings(
    payload: dict[str, Any], requirements: dict[str, Any]
) -> list[Finding]:
    signature_present = _get_field(payload, "appraiser.signature_present")
    signature_date = _get_field(payload, "appraiser.signature_date")
    if not signature_present or _is_missing(signature_date):
        return []

    config = requirements.get("photos", {}) if requirements else {}
    if isinstance(config, list):
        photo_entries = config
    else:
        photo_entries = config.get("required", []) if isinstance(config, dict) else []

    missing_codes: list[str] = []

    for entry in photo_entries:
        if not isinstance(entry, dict):
            continue
        azure_code = entry.get("azure_code") or entry.get("azure")
        payload_path = entry.get("payload_path") or entry.get("path")
        if not azure_code or not payload_path:
            continue
        value = _get_field(payload, payload_path)
        if isinstance(value, bool):
            if not value:
                missing_codes.append(str(azure_code))
            continue
        if _is_missing(value):
            missing_codes.append(str(azure_code))

    if not missing_codes:
        return []

    missing_codes.sort()
    missing_text = ", ".join(missing_codes)
    message = (
        "Photo inventory is incomplete for a signed report. "
        f"Missing Azure fields: {missing_text}."
    )
    return [
        Finding(
            field="photos",
            message=message,
            severity="error",
            rule="R-02",
        )
    ]


def validate(payload: dict[str, Any], schema_path: str, registry_path: str) -> dict[str, Any]:
    schema = _load_json(schema_path)
    registry = _load_json(registry_path)
    signature_requirements: dict[str, Any] = {}
    try:
        signature_requirements = _load_json(SIGNATURE_REQUIREMENTS_PATH)
    except FileNotFoundError:
        signature_requirements = {}
    photo_requirements: dict[str, Any] = {}
    try:
        photo_requirements = _load_json(PHOTO_REQUIREMENTS_PATH)
    except FileNotFoundError:
        photo_requirements = {}
    findings: list[Finding] = []

    findings.extend(_schema_findings(payload, schema))

    context = {k: _to_attr(v) for k, v in payload.items()}

    findings.extend(_field_requirements(payload, registry, context))
    findings.extend(_cross_rule_findings(payload, registry, context))
    findings.extend(_source_alignment_findings(payload, registry))
    findings.extend(_signature_requirement_findings(payload, signature_requirements))
    findings.extend(_photo_inventory_findings(payload, photo_requirements))

    status = "fail" if any(f.severity == "error" for f in findings) else "pass"
    return {
        "status": status,
        "findings": [f.as_dict() for f in findings],
        "ruleset_version": RULESET_VERSION,
    }
