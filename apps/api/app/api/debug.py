"""Temporary debug routes for infrastructure verification."""

import os
from urllib.parse import urlparse

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


def _safe_endpoint_diagnostics(endpoint_url: str | None):
    parsed = urlparse(endpoint_url or "")
    endpoint_text = endpoint_url if isinstance(endpoint_url, str) else ""
    return {
        "endpoint_length": len(endpoint_text),
        "endpoint_repr": repr(endpoint_text),
        "scheme": parsed.scheme,
        "hostname": parsed.hostname,
        "has_leading_whitespace": endpoint_text.startswith(" ") or endpoint_text.startswith("\t") or endpoint_text.startswith("\n"),
        "has_trailing_whitespace": endpoint_text.endswith(" ") or endpoint_text.endswith("\t") or endpoint_text.endswith("\n"),
        "starts_with_https": endpoint_text.startswith("https://"),
        "boto3_version": __import__("boto3").__version__,
        "botocore_version": __import__("botocore").__version__,
    }


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

    diagnostics = _safe_endpoint_diagnostics(endpoint_url)

    if not endpoint_url or not access_key or not secret_key or not bucket_name:
        raise ValueError("Missing required S3 configuration")

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        use_ssl=True,
    )

    diagnostics["client_endpoint_url"] = client.meta.endpoint_url
    return client, bucket_name, diagnostics


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
    settings = get_settings()
    endpoint_url = settings.s3_endpoint_url or os.getenv("S3_ENDPOINT_URL")
    diagnostics = _safe_endpoint_diagnostics(endpoint_url)
    try:
        client, bucket_name, diagnostics = _build_r2_client()
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

        final_diagnostics = _safe_endpoint_diagnostics(endpoint_url)
        final_diagnostics.update({
            "status": "diagnostic_failure",
            "error_type": error_type,
            "error": error_message,
        })

        return final_diagnostics
