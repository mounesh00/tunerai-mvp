"""Common response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "tunerai-api"
    version: str = "0.1.0"
    environment: str = "development"


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
