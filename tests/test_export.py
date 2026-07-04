"""Tests for tweetmentor.export (pure logic, filesystem via tmp_path only)."""

from __future__ import annotations

import csv
import json

import pytest

from tweetmentor.export import ExportError, json_to_csv


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_json_to_csv_with_list_of_objects(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]), encoding="utf-8")

    out = json_to_csv(input_path)

    assert out == input_path.with_suffix(".csv")
    rows = _read_csv(out)
    assert rows == [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]


def test_json_to_csv_with_single_object(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(json.dumps({"a": 1, "b": "x"}), encoding="utf-8")

    out = json_to_csv(input_path)

    rows = _read_csv(out)
    assert rows == [{"a": "1", "b": "x"}]


def test_json_to_csv_raises_for_scalar_top_level(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(json.dumps("just a string"), encoding="utf-8")

    with pytest.raises(ExportError, match="object or an array"):
        json_to_csv(input_path)


def test_json_to_csv_raises_when_array_item_is_not_object(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(json.dumps([{"a": 1}, "not-an-object"]), encoding="utf-8")

    with pytest.raises(ExportError, match="must be an object"):
        json_to_csv(input_path)


def test_json_to_csv_raises_when_file_missing(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        json_to_csv(missing)


def test_json_to_csv_flattens_nested_values(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(
        json.dumps([{"a": {"nested": True}, "b": [1, 2, 3]}]),
        encoding="utf-8",
    )

    out = json_to_csv(input_path)

    rows = _read_csv(out)
    assert rows[0]["a"] == json.dumps({"nested": True}, ensure_ascii=False)
    assert rows[0]["b"] == json.dumps([1, 2, 3], ensure_ascii=False)


def test_json_to_csv_collects_fieldnames_in_first_seen_order_across_records(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(
        json.dumps([{"a": 1, "b": 2}, {"b": 3, "c": 4}]),
        encoding="utf-8",
    )

    out = json_to_csv(input_path)

    with open(out, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == ["a", "b", "c"]


def test_json_to_csv_uses_explicit_output_path(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(json.dumps([{"a": 1}]), encoding="utf-8")
    output_path = tmp_path / "nested" / "out.csv"

    out = json_to_csv(input_path, output_path)

    assert out == output_path
    assert output_path.exists()


def test_json_to_csv_empty_list_produces_header_only_file(tmp_path):
    input_path = tmp_path / "data.json"
    input_path.write_text(json.dumps([]), encoding="utf-8")

    out = json_to_csv(input_path)

    assert out.exists()
    assert _read_csv(out) == []
