# Evaluation Engine

Every successful training run produces a **base vs tuned** comparison.

## Principles

1. Prefer deterministic metrics (keyword match, safety refusal cues).
2. LLM-as-judge may be secondary only — never the sole signal.
3. If the tuned model does not improve the benchmark, TunerAI reports:
   > "Tuning did not improve this benchmark."
4. Never invent or inflate results.

## Default cybersec benchmark

Held-out educational items covering:

- Domain knowledge (SSRF, XSS, SQL injection, CSRF, TLS)
- Factual distinctions (auth vs authorization)
- Instruction following
- Safety (refusal of unauthorized access requests)

## Output shape

```json
{
  "base": { "overall": 0.62, "category_scores": {...} },
  "tuned": { "overall": 0.78, "category_scores": {...} },
  "overall_delta": 0.16,
  "improvement": true,
  "regression_detected": false,
  "summary": "...",
  "methodology": "Deterministic keyword/safety heuristics on a fixed held-out set."
}
```

## Code

- `ml/evaluation/engine.py` — scoring + comparison
- Worker attaches results to `TrainingRun.metrics` and `ModelVersion.evaluation_results`
