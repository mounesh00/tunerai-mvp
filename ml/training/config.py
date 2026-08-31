"""Training configuration presets and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Literal, Optional


PresetName = Literal["fast", "balanced", "quality", "custom"]
StrategyName = Literal["qlora", "lora", "sft"]


# Supported open-weight instruct models for v0.1 (small enough for demos)
SUPPORTED_BASE_MODELS = [
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
]


@dataclass
class TrainingHyperParams:
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    warmup_ratio: float = 0.03
    scheduler: str = "cosine"
    eval_steps: int = 50
    save_steps: int = 100
    logging_steps: int = 10
    max_grad_norm: float = 1.0
    weight_decay: float = 0.01
    optim: str = "paged_adamw_8bit"
    # QLoRA
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"
    use_double_quant: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PRESETS: Dict[str, TrainingHyperParams] = {
    "fast": TrainingHyperParams(
        epochs=1,
        learning_rate=3e-4,
        batch_size=8,
        gradient_accumulation_steps=2,
        lora_rank=8,
        lora_alpha=16,
        max_seq_length=1024,
    ),
    "balanced": TrainingHyperParams(
        epochs=3,
        learning_rate=2e-4,
        batch_size=4,
        gradient_accumulation_steps=4,
        lora_rank=16,
        lora_alpha=32,
        max_seq_length=2048,
    ),
    "quality": TrainingHyperParams(
        epochs=5,
        learning_rate=1e-4,
        batch_size=2,
        gradient_accumulation_steps=8,
        lora_rank=32,
        lora_alpha=64,
        max_seq_length=2048,
        lora_dropout=0.05,
    ),
}


def resolve_config(
    preset: Optional[str] = "balanced",
    strategy: StrategyName = "qlora",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if preset and preset != "custom" and preset in PRESETS:
        params = PRESETS[preset]
    else:
        params = TrainingHyperParams()
    cfg = params.to_dict()
    if overrides:
        for k, v in overrides.items():
            if k in cfg and v is not None:
                cfg[k] = v
    cfg["strategy"] = strategy
    cfg["preset"] = preset or "custom"
    return cfg


def estimate_resources(
    base_model: str,
    num_train_samples: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Rough resource estimates — labeled as estimates, not guarantees."""
    # Heuristic VRAM by model size keyword
    name = base_model.lower()
    if "0.5b" in name or "1.1b" in name or "tinyllama" in name:
        base_vram = 6.0
    elif "1.5b" in name or "phi-3-mini" in name:
        base_vram = 10.0
    elif "3b" in name:
        base_vram = 14.0
    elif "7b" in name:
        base_vram = 18.0
    else:
        base_vram = 16.0

    if config.get("strategy") == "qlora" or config.get("load_in_4bit"):
        vram = base_vram
    elif config.get("strategy") == "lora":
        vram = base_vram * 1.4
    else:
        vram = base_vram * 2.5

    seq = int(config.get("max_seq_length", 2048))
    batch = int(config.get("batch_size", 4))
    accum = int(config.get("gradient_accumulation_steps", 4))
    epochs = int(config.get("epochs", 3))
    effective_batch = batch * accum
    steps_per_epoch = max(1, num_train_samples // effective_batch)
    total_steps = steps_per_epoch * epochs
    # ~0.8–2 sec/step rough for small models on consumer GPU
    sec_per_step = 1.2 if "0.5b" in name or "1.1b" in name else 2.0
    minutes = (total_steps * sec_per_step) / 60.0
    # Placeholder cost: $0.50/GPU-hour consumer-class estimate
    cost = (minutes / 60.0) * 0.50
    storage_gb = 0.5 + (config.get("lora_rank", 16) / 16) * 0.3

    return {
        "estimated_vram_gb": round(vram, 1),
        "estimated_time_minutes": round(minutes, 1),
        "estimated_cost_usd": round(cost, 2),
        "estimated_storage_gb": round(storage_gb, 2),
        "total_steps": total_steps,
        "note": "Estimates only — actual time/VRAM depend on hardware and data.",
    }
