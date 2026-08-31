"""
Dataset validation and quality analysis for TunerAI.

Pipeline:
  Upload → Validate schema → Parse → Normalize → Detect duplicates/malformed
  → Token estimates → Length distribution → Quality score → Train/val split

Never silently discards records. Always reports what was removed and why.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Approximate tokens: ~4 chars per token for English-ish text (rough estimate).
CHARS_PER_TOKEN = 4.0


@dataclass
class RecordIssue:
    line_number: int
    reason: str
    snippet: Optional[str] = None


@dataclass
class ValidationResult:
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicate_count: int = 0
    duplicate_percentage: float = 0.0
    avg_tokens: float = 0.0
    max_tokens: int = 0
    estimated_training_tokens: int = 0
    train_size: int = 0
    validation_size: int = 0
    quality_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    issues: List[RecordIssue] = field(default_factory=list)
    format_detected: str = "unknown"  # instruction | messages | mixed
    length_distribution: Dict[str, int] = field(default_factory=dict)
    # Normalized records ready for training (train + val already split conceptually)
    valid_records_data: List[Dict[str, Any]] = field(default_factory=list)
    train_records: List[Dict[str, Any]] = field(default_factory=list)
    validation_records: List[Dict[str, Any]] = field(default_factory=list)

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "duplicate_count": self.duplicate_count,
            "duplicate_percentage": round(self.duplicate_percentage, 2),
            "avg_tokens": round(self.avg_tokens, 1),
            "max_tokens": self.max_tokens,
            "estimated_training_tokens": self.estimated_training_tokens,
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            "quality_score": round(self.quality_score, 1),
            "warnings": self.warnings,
            "format_detected": self.format_detected,
            "length_distribution": self.length_distribution,
            "issues_sample": [
                {"line": i.line_number, "reason": i.reason, "snippet": i.snippet}
                for i in self.issues[:50]
            ],
            "issues_total": len(self.issues),
        }


class DatasetValidator:
    """Validate and score JSONL instruction / chat datasets."""

    def __init__(
        self,
        max_seq_length: int = 2048,
        validation_split: float = 0.1,
        min_records: int = 10,
        max_duplicate_pct: float = 30.0,
    ):
        self.max_seq_length = max_seq_length
        self.validation_split = validation_split
        self.min_records = min_records
        self.max_duplicate_pct = max_duplicate_pct

    def validate_text(self, content: str, filename: str = "dataset.jsonl") -> ValidationResult:
        result = ValidationResult()
        lines = content.splitlines()
        seen_hashes: Dict[str, int] = {}
        token_counts: List[int] = []
        formats: Dict[str, int] = {"instruction": 0, "messages": 0}

        for line_no, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line:
                continue

            result.total_records += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                result.invalid_records += 1
                result.issues.append(
                    RecordIssue(line_no, f"Invalid JSON: {e.msg}", snippet=line[:120])
                )
                continue

            if not isinstance(obj, dict):
                result.invalid_records += 1
                result.issues.append(
                    RecordIssue(line_no, "Record is not a JSON object", snippet=line[:120])
                )
                continue

            normalized, fmt, err = self._normalize_record(obj)
            if err:
                result.invalid_records += 1
                result.issues.append(RecordIssue(line_no, err, snippet=line[:120]))
                continue

            formats[fmt] = formats.get(fmt, 0) + 1

            # Duplicate detection on normalized content
            content_hash = self._hash_record(normalized)
            if content_hash in seen_hashes:
                result.duplicate_count += 1
                result.issues.append(
                    RecordIssue(
                        line_no,
                        f"Duplicate of line {seen_hashes[content_hash]}",
                        snippet=line[:80],
                    )
                )
                # Still count as valid structure but mark duplicate
                continue

            seen_hashes[content_hash] = line_no

            tokens = self._estimate_tokens(normalized)
            if tokens > self.max_seq_length * 1.5:
                result.warnings.append(
                    f"Line {line_no}: estimated {tokens} tokens exceeds soft limit "
                    f"({self.max_seq_length})"
                )

            token_counts.append(tokens)
            result.valid_records_data.append(normalized)
            result.valid_records += 1

        # Format detection
        if formats["instruction"] and formats["messages"]:
            result.format_detected = "mixed"
        elif formats["messages"]:
            result.format_detected = "messages"
        elif formats["instruction"]:
            result.format_detected = "instruction"
        else:
            result.format_detected = "unknown"

        # Stats
        if token_counts:
            result.avg_tokens = sum(token_counts) / len(token_counts)
            result.max_tokens = max(token_counts)
            result.estimated_training_tokens = sum(token_counts)
            result.length_distribution = self._bucket_lengths(token_counts)

        if result.total_records > 0:
            result.duplicate_percentage = (
                result.duplicate_count / result.total_records
            ) * 100.0

        # Train / validation split (deterministic by hash for reproducibility)
        result.train_records, result.validation_records = self._split(
            result.valid_records_data
        )
        result.train_size = len(result.train_records)
        result.validation_size = len(result.validation_records)

        # Quality score & warnings
        result.quality_score = self._compute_quality_score(result)
        self._add_quality_warnings(result)

        return result

    def _normalize_record(
        self, obj: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """Normalize to either instruction format or messages format."""
        if "messages" in obj:
            messages = obj["messages"]
            if not isinstance(messages, list) or len(messages) < 2:
                return None, "messages", "messages must be a list with at least 2 turns"
            normalized_msgs = []
            for m in messages:
                if not isinstance(m, dict):
                    return None, "messages", "Each message must be an object"
                role = m.get("role")
                content = m.get("content")
                if role not in ("system", "user", "assistant"):
                    return None, "messages", f"Invalid role: {role}"
                if not isinstance(content, str) or not content.strip():
                    return None, "messages", "Message content must be non-empty string"
                normalized_msgs.append({"role": role, "content": content.strip()})
            # Require at least one user and one assistant
            roles = {m["role"] for m in normalized_msgs}
            if "user" not in roles or "assistant" not in roles:
                return None, "messages", "Need at least one user and one assistant message"
            return {"messages": normalized_msgs}, "messages", None

        if "instruction" in obj or "output" in obj or "response" in obj:
            instruction = obj.get("instruction") or obj.get("prompt") or ""
            input_text = obj.get("input") or obj.get("context") or ""
            output = obj.get("output") or obj.get("response") or obj.get("completion") or ""
            if not isinstance(instruction, str) or not instruction.strip():
                return None, "instruction", "instruction/prompt must be non-empty string"
            if not isinstance(output, str) or not output.strip():
                return None, "instruction", "output/response must be non-empty string"
            if not isinstance(input_text, str):
                input_text = str(input_text) if input_text is not None else ""
            return {
                "instruction": instruction.strip(),
                "input": input_text.strip(),
                "output": output.strip(),
            }, "instruction", None

        return None, "unknown", "Unrecognized format: need 'messages' or 'instruction'+'output'"

    def _hash_record(self, record: Dict[str, Any]) -> str:
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _estimate_tokens(self, record: Dict[str, Any]) -> int:
        if "messages" in record:
            text = " ".join(m["content"] for m in record["messages"])
        else:
            text = " ".join(
                [
                    record.get("instruction", ""),
                    record.get("input", ""),
                    record.get("output", ""),
                ]
            )
        # Rough char-based estimate; real tokenizer used later in training
        return max(1, int(len(text) / CHARS_PER_TOKEN))

    def _bucket_lengths(self, counts: List[int]) -> Dict[str, int]:
        buckets = {
            "0-128": 0,
            "129-512": 0,
            "513-1024": 0,
            "1025-2048": 0,
            "2049+": 0,
        }
        for t in counts:
            if t <= 128:
                buckets["0-128"] += 1
            elif t <= 512:
                buckets["129-512"] += 1
            elif t <= 1024:
                buckets["513-1024"] += 1
            elif t <= 2048:
                buckets["1025-2048"] += 1
            else:
                buckets["2049+"] += 1
        return buckets

    def _split(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if len(records) < 5:
            return records, []
        # Deterministic split by content hash
        train, val = [], []
        for r in records:
            h = int(self._hash_record(r)[:8], 16)
            if (h % 1000) / 1000.0 < self.validation_split:
                val.append(r)
            else:
                train.append(r)
        if not val and records:
            # Ensure at least one val example when possible
            val.append(train.pop())
        return train, val

    def _compute_quality_score(self, result: ValidationResult) -> float:
        """Score 0–100 based on validity, size, duplicates, length diversity."""
        if result.total_records == 0:
            return 0.0

        validity = result.valid_records / result.total_records  # 0–1
        size_score = min(1.0, result.valid_records / max(self.min_records * 5, 50))
        dup_penalty = min(1.0, result.duplicate_percentage / 100.0)
        length_ok = 1.0
        if result.max_tokens > self.max_seq_length * 2:
            length_ok = 0.5
        elif result.avg_tokens < 10:
            length_ok = 0.6

        score = (
            validity * 40
            + size_score * 25
            + (1.0 - dup_penalty) * 20
            + length_ok * 15
        )
        return max(0.0, min(100.0, score))

    def _add_quality_warnings(self, result: ValidationResult) -> None:
        if result.valid_records < self.min_records:
            result.warnings.append(
                f"Only {result.valid_records} valid records; recommend at least "
                f"{self.min_records} for meaningful fine-tuning."
            )
        if result.duplicate_percentage > self.max_duplicate_pct:
            result.warnings.append(
                f"High duplicate rate ({result.duplicate_percentage:.1f}%). "
                "Consider deduplicating before training."
            )
        if result.validation_size == 0:
            result.warnings.append(
                "No validation split created (dataset too small). "
                "Evaluation quality may be limited."
            )
        if result.format_detected == "mixed":
            result.warnings.append(
                "Mixed instruction and messages formats detected. "
                "Prefer a single format for consistent training."
            )
        if result.invalid_records > 0:
            result.warnings.append(
                f"{result.invalid_records} record(s) were invalid and excluded. "
                "See issues_sample in the report."
            )
