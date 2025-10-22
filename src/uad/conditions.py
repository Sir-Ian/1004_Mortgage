from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

CONDITION_RANKS: dict[str, int] = {
    "C1": 1,
    "C2": 2,
    "C3": 3,
    "C4": 4,
    "C5": 5,
    "C6": 6,
}

_CONDITION_CODE_PATTERN = re.compile(r"C([1-6])", re.IGNORECASE)


def normalize_condition_code(value: Any) -> str | None:
    """Normalize various condition inputs to canonical C1–C6 codes."""

    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip().upper()
        match = _CONDITION_CODE_PATTERN.search(trimmed)
        if match:
            return f"C{match.group(1)}"
        return None
    return None


def condition_rank(value: Any) -> int | None:
    """Resolve a condition code or rank into its numeric rank."""

    if value is None:
        return None
    if isinstance(value, int | float):
        integer = int(value)
        if 1 <= integer <= 6:
            return integer
        return None
    if isinstance(value, str):
        code = normalize_condition_code(value)
        if code is None:
            return None
        return CONDITION_RANKS.get(code)
    if isinstance(value, dict):
        # Try rank first to support payload structures like {"condition_rank": 3}.
        rank_value = value.get("condition_rank")
        resolved = condition_rank(rank_value)
        if resolved is not None:
            return resolved
        code_value = value.get("condition") or value.get("code")
        return condition_rank(code_value)
    return None


def condition_stats(ranks: Iterable[int]) -> tuple[float, float]:
    """Return the mean and population standard deviation for the given ranks."""

    values = [int(rank) for rank in ranks]
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std_dev = math.sqrt(variance)
    return mean, std_dev
