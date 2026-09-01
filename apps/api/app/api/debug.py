"""Temporary debug routes for infrastructure verification."""

import os

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(
    prefix="/debug",
    tags=["debug"],
)


def _coerce_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _build_r2_client():
    settings = get_settings()

    endpoint_url = settings.s3_endpoint_url or os.getenv("S3_ENDPOINT_URL")
    access_key = settings.s3_access_key or os.getenv("S3_ACCESS_KEY")
    secret_key = settings.s3_secret_key or os.getenv("S3_SECRET_KEY")
    bucket_name = settings.s3_bucket_name or os.getenv("S3_BUCKET_NAME")
    use_ssl = settings.s3_use_ssl
    use_ssl_value = os.getenv("S3_USE_SSL")
    if use_ssl_value is not None:
        use_ssl = _coerce_bool(use_ssl_value)

    if not endpoint_url or not access_key or not secret_key or not bucket_name:
        raise ValueError("Missing required S3 configuration")

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=settings.s3_region,
        use_ssl=use_ssl,
    )
    return client, bucket_name


# TEMPORARY: Infrastructure verification endpoint.
# Remove before production release.
@router.get("/ping")
async def debug_ping():
    return {
        "status": "ok",
        "message": "Debug router is registered",
    }


# TEMPORARY: Infrastructure verification endpoint.
# Remove before production release.
@router.get("/r2-check")
async def debug_r2_check():
    try:
        client, bucket_name = _build_r2_client()
        response = client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=1,
        )
        key_count = int(response.get("KeyCount", 0))

        return {
            "status": "success",
            "r2_connection": True,
            "bucket": bucket_name,
            "key_count": key_count,
        }
    except Exception as exc:  # pragma: no cover - debug only
        error_type = type(exc).__name__
        error_message = str(exc).strip()
        if len(error_message) > 200:
            error_message = error_message[:197] + "..."

        return {
            "status": "failed",
            "r2_connection": False,
            "error_type": error_type,
            "error": error_message,
        }
