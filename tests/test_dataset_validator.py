"""Unit tests for dataset validation pipeline."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from ml.data.validator import DatasetValidator


def test_instruction_format():
    content = "\n".join(
        [
            '{"instruction": "What is SSRF?", "input": "", "output": "Server-Side Request Forgery."}',
            '{"instruction": "What is XSS?", "input": "web", "output": "Cross-site scripting."}',
            '{"instruction": "What is CSRF?", "output": "Cross-site request forgery."}',
        ]
    )
    r = DatasetValidator(min_records=2).validate_text(content)
    assert r.total_records == 3
    assert r.valid_records == 3
    assert r.invalid_records == 0
    assert r.format_detected == "instruction"
    assert r.quality_score > 40


def test_messages_format():
    content = (
        '{"messages": [{"role": "user", "content": "Explain SSRF"}, '
        '{"role": "assistant", "content": "SSRF lets attackers abuse the server."}]}'
    )
    r = DatasetValidator(min_records=1).validate_text(content)
    assert r.valid_records == 1
    assert r.format_detected == "messages"


def test_invalid_and_duplicates():
    content = "\n".join(
        [
            '{"instruction": "Q1", "output": "A1"}',
            '{"instruction": "Q1", "output": "A1"}',  # duplicate
            "not-json",
            '{"instruction": "missing output"}',
            '{"messages": [{"role": "user", "content": "hi"}]}',  # incomplete
        ]
    )
    r = DatasetValidator(min_records=1).validate_text(content)
    assert r.total_records == 5
    assert r.valid_records == 1
    assert r.duplicate_count == 1
    assert r.invalid_records >= 2
    assert len(r.issues) >= 3


def test_never_silent_discard():
    content = '{"instruction": "x", "output": "y"}\nbad line\n'
    r = DatasetValidator(min_records=1).validate_text(content)
    assert r.invalid_records == 1
    assert any("Invalid JSON" in i.reason or "JSON" in i.reason for i in r.issues)


def test_quality_report_keys():
    content = '{"instruction": "What is a firewall?", "output": "Network security device."}\n' * 15
    r = DatasetValidator().validate_text(content)
    report = r.to_report_dict()
    for key in (
        "total_records",
        "valid_records",
        "quality_score",
        "train_size",
        "validation_size",
        "warnings",
        "length_distribution",
    ):
        assert key in report


if __name__ == "__main__":
    test_instruction_format()
    test_messages_format()
    test_invalid_and_duplicates()
    test_never_silent_discard()
    test_quality_report_keys()
    print("All dataset validator tests passed.")
