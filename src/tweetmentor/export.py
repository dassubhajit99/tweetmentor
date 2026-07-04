"""Convert a JSON file into a CSV file.

The input JSON must be either a list of objects or a single object. Nested
objects/lists are serialized as JSON text in their cell.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


class ExportError(ValueError):
    """Raised when the input JSON can't be turned into tabular rows."""


def _load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ExportError("JSON top level must be an object or an array of objects.")


def _collect_fieldnames(records: list[dict]) -> list[str]:
    """Collect column names in first-seen order across all records."""
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ExportError("Every item in the JSON array must be an object.")
        for key in record:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    return fieldnames


def _flatten_value(value):
    """Turn nested structures into a string so they fit in a CSV cell."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def json_to_csv(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Write ``input_path`` (JSON) to CSV, returning the output path.

    If ``output_path`` is omitted, the input name with a ``.csv`` suffix is used.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"file not found: {input_path}")

    out = Path(output_path) if output_path else input_path.with_suffix(".csv")

    records = _load_json(input_path)
    fieldnames = _collect_fieldnames(records)

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: _flatten_value(v) for k, v in record.items()})
    return out
