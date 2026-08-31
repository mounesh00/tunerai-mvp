"""OpenAI-compatible inference endpoint."""

from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from app.api.deps import DbSession
from app.schemas.deployment import ChatCompletionRequest
from app.services import deployment as deployment_service
from ml.inference.openai_api import global_inference

router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    db: DbSession,
    authorization: Optional[str] = Header(None),
):
    """
    OpenAI-compatible chat completions.

    Model id format: tunerai/<endpoint_slug>
    Auth: Bearer <api_key> (optional in v0.1 dev; recommended for production)
    """
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        key = await deployment_service.verify_api_key(db, raw)
        if key is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

    model_id = body.model
    if not model_id.startswith("tunerai/"):
        # Allow direct registration for local demo
        global_inference.register_mock(model_id)

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    try:
        return global_inference.generate(
            model_id,
            messages,
            max_tokens=body.max_tokens or 512,
            temperature=body.temperature or 0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
