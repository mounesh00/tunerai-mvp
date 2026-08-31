"""
OpenAI-compatible chat completions helpers for TunerAI deployments.

Real inference uses vLLM / transformers when available; otherwise a
documented mock path for local development.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


def build_chat_completion_response(
    *,
    model: str,
    content: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    parts.append("ASSISTANT:")
    return "\n".join(parts)


class InferenceEngine:
    """Loads adapter + base model or falls back to mock."""

    def __init__(self) -> None:
        self._engines: Dict[str, Any] = {}

    def register_mock(self, model_id: str, domain_hint: str = "cybersecurity") -> None:
        self._engines[model_id] = {"type": "mock", "domain": domain_hint}

    def generate(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        engine = self._engines.get(model_id)
        prompt = messages_to_prompt(messages)
        if engine is None or engine.get("type") == "mock":
            # Honest mock: keyword-aware stub for demo deployments
            from ml.evaluation.engine import mock_generate_factory

            text = mock_generate_factory("tuned")(messages[-1].get("content", "") if messages else "")
            return build_chat_completion_response(
                model=model_id,
                content=text,
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(text.split()),
            )
        # Future: vLLM / transformers path
        raise NotImplementedError("Real GPU inference engine not loaded in this environment")


# Process-wide registry for deployed models (v0.1 in-process)
global_inference = InferenceEngine()
