"""Tests for training config presets and estimates."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.training.config import PRESETS, estimate_resources, resolve_config
from ml.training.pipeline import run_training


def test_presets():
    for name in ("fast", "balanced", "quality"):
        cfg = resolve_config(preset=name, strategy="qlora")
        assert cfg["preset"] == name
        assert cfg["epochs"] >= 1
        assert cfg["lora_rank"] >= 8


def test_estimate_has_disclaimer():
    cfg = resolve_config(preset="fast")
    est = estimate_resources("Qwen/Qwen2.5-0.5B-Instruct", 100, cfg)
    assert "estimated_vram_gb" in est
    assert "note" in est
    assert "estimate" in est["note"].lower()


def test_dry_run_training():
    records = [
        {"instruction": "What is SSRF?", "input": "", "output": "Server-Side Request Forgery."}
        for _ in range(5)
    ]
    result = run_training(
        base_model="Qwen/Qwen2.5-0.5B-Instruct",
        train_records=records,
        eval_records=[],
        config=resolve_config(preset="fast"),
        output_dir="/tmp/tunerai-test-run",
        dry_run=True,
    )
    assert result["status"] == "COMPLETED"
    assert result["dry_run"] is True
    assert result["adapter_path"]


if __name__ == "__main__":
    test_presets()
    test_estimate_has_disclaimer()
    test_dry_run_training()
    print("All training config tests passed.")
