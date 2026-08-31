"""TunerAI FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("starting_tunerai_api", env=settings.app_env, debug=settings.app_debug)
    yield
    logger.info("shutting_down_tunerai_api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="TunerAI — Domain-adaptation platform for open-source LLMs",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # OpenAI-compatible alias: POST /v1/chat/completions
    from app.api.v1.inference import router as inference_router

    app.include_router(inference_router, prefix="/v1", tags=["inference-openai"])

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": "0.1.0",
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
            "chat_completions": "/v1/chat/completions",
        }

    @app.get("/health")
    async def root_health():
        return {"status": "healthy", "service": "tunerai-api", "version": "0.1.0"}

    return app


app = create_app()
