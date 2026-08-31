"""
QLoRA / LoRA SFT training pipeline.

- Real path: uses PEFT + TRL + bitsandbytes when CUDA + libs available.
- Dry-run path: simulates training progress for CI / machines without GPU.

Never claims success without either a real adapter artifact or an explicit dry-run flag.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str, Optional[Dict[str, Any]]], None]


def _has_cuda() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def _libs_available() -> bool:
    try:
        import transformers  # noqa: F401
        import peft  # noqa: F401
        import trl  # noqa: F401

        return True
    except ImportError:
        return False


def run_training(
    *,
    base_model: str,
    train_records: List[Dict[str, Any]],
    eval_records: List[Dict[str, Any]],
    config: Dict[str, Any],
    output_dir: str,
    dry_run: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """
    Execute SFT with LoRA/QLoRA.

    Returns artifact metadata dict with keys:
      status, adapter_path, train_loss, eval_loss, metrics, dry_run
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    def report(p: float, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if progress_cb:
            progress_cb(p, msg, extra)
        logger.info("train_progress %.0f%% %s", p * 100, msg)

    force_dry = dry_run or os.environ.get("TUNERAI_DRY_RUN", "").lower() in ("1", "true", "yes")
    use_real = (not force_dry) and _has_cuda() and _libs_available()

    if not use_real:
        return _dry_run_train(
            base_model=base_model,
            train_records=train_records,
            config=config,
            output_path=output_path,
            report=report,
            reason="dry_run" if force_dry else "no_cuda_or_libs",
        )

    return _real_train(
        base_model=base_model,
        train_records=train_records,
        eval_records=eval_records,
        config=config,
        output_path=output_path,
        report=report,
    )


def _dry_run_train(
    *,
    base_model: str,
    train_records: List[Dict[str, Any]],
    config: Dict[str, Any],
    output_path: Path,
    report: ProgressCallback,
    reason: str,
) -> Dict[str, Any]:
    """Simulate training for environments without GPU / ML stack."""
    epochs = int(config.get("epochs", 1))
    report(0.05, f"Dry-run training ({reason}): preparing {len(train_records)} samples")
    time.sleep(0.3)
    losses = []
    for ep in range(epochs):
        loss = 2.0 - (ep + 1) * (0.3 / max(epochs, 1))
        losses.append(loss)
        report(
            0.1 + 0.7 * ((ep + 1) / epochs),
            f"Epoch {ep + 1}/{epochs} (simulated) loss={loss:.3f}",
            {"epoch": ep + 1, "train_loss": loss},
        )
        time.sleep(0.4)
    report(0.9, "Packaging simulated adapter")
    adapter_dir = output_path / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "base_model": base_model,
        "strategy": config.get("strategy", "qlora"),
        "dry_run": True,
        "reason": reason,
        "num_samples": len(train_records),
        "config": config,
    }
    (adapter_dir / "adapter_config.json").write_text(json.dumps(meta, indent=2))
    (adapter_dir / "README.txt").write_text(
        "DRY-RUN adapter placeholder. Re-run with CUDA + PEFT/TRL for a real adapter.\n"
    )
    report(1.0, "Dry-run complete")
    return {
        "status": "COMPLETED",
        "adapter_path": str(adapter_dir),
        "train_loss": losses[-1] if losses else None,
        "eval_loss": (losses[-1] * 1.05) if losses else None,
        "metrics": {"epochs": epochs, "dry_run": True, "reason": reason},
        "dry_run": True,
    }


def _real_train(
    *,
    base_model: str,
    train_records: List[Dict[str, Any]],
    eval_records: List[Dict[str, Any]],
    config: Dict[str, Any],
    output_path: Path,
    report: ProgressCallback,
) -> Dict[str, Any]:
    """Real QLoRA/LoRA training path."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from trl import SFTTrainer

    report(0.05, f"Loading tokenizer/model: {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = None
    strategy = config.get("strategy", "qlora")
    if strategy == "qlora" and config.get("load_in_4bit", True):
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=config.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_use_double_quant=config.get("use_double_quant", True),
            bnb_4bit_compute_dtype=getattr(
                torch, config.get("bnb_4bit_compute_dtype", "bfloat16"), torch.bfloat16
            ),
        )

    model_kwargs: Dict[str, Any] = {"trust_remote_code": True, "device_map": "auto"}
    if bnb_config is not None:
        model_kwargs["quantization_config"] = bnb_config

    model = AutoModelForCausalLM.from_pretrained(base_model, **model_kwargs)
    if bnb_config is not None:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=int(config.get("lora_rank", 16)),
        lora_alpha=int(config.get("lora_alpha", 32)),
        lora_dropout=float(config.get("lora_dropout", 0.05)),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)

    def to_text(rec: Dict[str, Any]) -> str:
        if "messages" in rec:
            parts = []
            for m in rec["messages"]:
                parts.append(f"{m['role'].upper()}: {m['content']}")
            return "\n".join(parts)
        instr = rec.get("instruction", "")
        inp = rec.get("input", "")
        out = rec.get("output", "")
        if inp:
            return f"### Instruction:\n{instr}\n\n### Input:\n{inp}\n\n### Response:\n{out}"
        return f"### Instruction:\n{instr}\n\n### Response:\n{out}"

    train_ds = Dataset.from_list([{"text": to_text(r)} for r in train_records])
    eval_ds = (
        Dataset.from_list([{"text": to_text(r)} for r in eval_records])
        if eval_records
        else None
    )

    report(0.15, f"Starting SFTTrainer ({strategy}) on {len(train_records)} samples")
    training_args = TrainingArguments(
        output_dir=str(output_path / "checkpoints"),
        num_train_epochs=int(config.get("epochs", 3)),
        per_device_train_batch_size=int(config.get("batch_size", 4)),
        gradient_accumulation_steps=int(config.get("gradient_accumulation_steps", 4)),
        learning_rate=float(config.get("learning_rate", 2e-4)),
        warmup_ratio=float(config.get("warmup_ratio", 0.03)),
        logging_steps=int(config.get("logging_steps", 10)),
        save_steps=int(config.get("save_steps", 100)),
        eval_strategy="steps" if eval_ds is not None else "no",
        eval_steps=int(config.get("eval_steps", 50)) if eval_ds is not None else None,
        fp16=False,
        bf16=True,
        optim=config.get("optim", "paged_adamw_8bit"),
        lr_scheduler_type=config.get("scheduler", "cosine"),
        max_grad_norm=float(config.get("max_grad_norm", 1.0)),
        weight_decay=float(config.get("weight_decay", 0.01)),
        report_to=[],
        save_total_limit=2,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
    )
    train_result = trainer.train()
    report(0.9, "Saving adapter")
    adapter_dir = output_path / "adapter"
    trainer.model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    metrics = dict(train_result.metrics) if train_result.metrics else {}
    report(1.0, "Training complete")
    return {
        "status": "COMPLETED",
        "adapter_path": str(adapter_dir),
        "train_loss": metrics.get("train_loss"),
        "eval_loss": metrics.get("eval_loss"),
        "metrics": metrics,
        "dry_run": False,
    }
