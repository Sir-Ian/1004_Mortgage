from __future__ import annotations

import os
from pathlib import Path

_QUOTE_CHARS = {"'", '"'}


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in _QUOTE_CHARS:
        return value[1:-1]
    return value


def load_env_file(path: Path | None = None, *, override: bool = False) -> None:
    """Load key=value pairs from a .env file into ``os.environ``.

    This intentionally avoids adding python-dotenv as a dependency while still supporting
    simple assignments and quoted values. Existing environment variables are preserved unless
    ``override`` is set to True.
    """

    env_path = path or Path(__file__).resolve().parents[1] / ".env"

    try:
        content = env_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not override and key in os.environ:
            continue
        raw_value = value.strip()
        quoted = (
            len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in _QUOTE_CHARS
        )
        cleaned = _strip_quotes(raw_value)
        # Support inline comments when the value is not quoted.
        if not quoted and " #" in cleaned:
            cleaned = cleaned.split(" #", 1)[0].rstrip()
        os.environ[key] = cleaned
