"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, datasets, deployments, health, inference, models, projects, training

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])
# OpenAI-compatible path: /api/v1/v1/chat/completions — also mount at root-friendly path
api_router.include_router(inference.router, prefix="/v1", tags=["inference"])
