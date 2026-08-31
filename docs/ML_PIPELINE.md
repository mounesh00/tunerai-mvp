# ML Pipeline

## Dataset validation

Location: `ml/data/validator.py`

### Accepted formats

**Instruction / SFT:**

```json
{"instruction": "...", "input": "...", "output": "..."}
```

Aliases: `prompt`→instruction, `response`/`completion`→output, `context`→input.

**Chat / messages:**

```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

Roles: `system`, `user`, `assistant`. At least one user and one assistant required.

### Pipeline steps

1. Parse JSONL line-by-line
2. Schema validation (never silent discard)
3. Normalize to canonical instruction or messages form
4. SHA-256 content hash for duplicate detection
5. Approximate token counts (chars/4; real tokenizer applied at training time)
6. Length distribution buckets
7. Deterministic train/validation split (~10% val by hash)
8. Quality score 0–100
9. Warnings for small size, high duplicates, mixed formats, oversize sequences

### Quality score factors

| Factor | Weight |
|--------|--------|
| Validity ratio | 40% |
| Dataset size | 25% |
| Low duplicate rate | 20% |
| Reasonable sequence lengths | 15% |

### API

- `POST /api/v1/datasets` — create dataset metadata
- `POST /api/v1/datasets/{id}/upload` — upload JSONL + run validation
- `GET /api/v1/datasets/{id}/versions/{vid}/report` — full quality report

## Training (planned Phase 4–5)

- Strategy: QLoRA / LoRA + SFT via PEFT + TRL
- Jobs: Celery worker, never in-request
- Presets: Fast / Balanced / Quality + advanced hyperparams

## Evaluation (planned Phase 6)

- Mandatory base vs tuned comparison
- Deterministic metrics preferred; LLM-as-judge secondary only
- Explicit regression reporting
