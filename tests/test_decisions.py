import csv
import json
from pathlib import Path
import pytest
import yaml
from source_identifier_banking.decisions import load_decisions, apply_decisions


def test_load_decisions_empty(tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text("candidate_id,decision,notes\n")
    result = load_decisions(str(csv_file))
    assert result == []


def test_load_decisions_with_rows(tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text("candidate_id,decision,notes\nabc123,add,good source\ndef456,reject,not relevant\n")
    result = load_decisions(str(csv_file))
    assert len(result) == 2
    assert result[0]["candidate_id"] == "abc123"
    assert result[0]["decision"] == "add"
    assert result[1]["decision"] == "reject"


def test_apply_decisions_add(tmp_path):
    candidates_file = tmp_path / "candidates.json"
    decisions_file = tmp_path / "decisions.csv"
    approved_file = tmp_path / "approved.yaml"
    rejected_file = tmp_path / "rejected.yaml"

    candidates = [{
        "candidate_id": "abc123",
        "source_name": "Test Regulator",
        "homepage_url": "https://test-regulator.gov",
        "feed_url": None,
        "jurisdiction": "US",
        "source_type": "regulator",
    }]
    candidates_file.write_text(json.dumps(candidates))
    decisions_file.write_text("candidate_id,decision,notes\nabc123,add,looks good\n")

    apply_decisions(str(decisions_file), str(candidates_file), str(approved_file), str(rejected_file))

    data = yaml.safe_load(approved_file.read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "Test Regulator"


def test_apply_decisions_reject(tmp_path):
    candidates_file = tmp_path / "candidates.json"
    decisions_file = tmp_path / "decisions.csv"
    approved_file = tmp_path / "approved.yaml"
    rejected_file = tmp_path / "rejected.yaml"

    candidates = [{
        "candidate_id": "xyz789",
        "source_name": "Bad Source",
        "homepage_url": "https://bad-source.com",
        "feed_url": None,
        "jurisdiction": "Unknown",
        "source_type": "unknown",
    }]
    candidates_file.write_text(json.dumps(candidates))
    decisions_file.write_text("candidate_id,decision,notes\nxyz789,reject,not relevant\n")

    apply_decisions(str(decisions_file), str(candidates_file), str(approved_file), str(rejected_file))

    data = yaml.safe_load(rejected_file.read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["name"] == "Bad Source"
