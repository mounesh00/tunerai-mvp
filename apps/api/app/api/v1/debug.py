"""Temporary debug endpoints for deployment verification."""

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/debug/r2-check")
async def r2_check() -> dict[str, object]:
    """TEMPORARY: verify configured R2 connectivity without exposing credentials."""
    settings = get_settings()
    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
        ) as client:
            response = await client.list_objects_v2(
                Bucket=settings.s3_bucket_name,
                MaxKeys=1,
            )
    except (BotoCoreError, ClientError) as error:
        return {
            "ok": False,
            "bucket": settings.s3_bucket_name or None,
            "error_type": type(error).__name__,
            "message": "Unable to reach configured object storage",
        }

    return {
        "ok": True,
        "bucket": settings.s3_bucket_name,
        "region": settings.s3_region or None,
        "endpoint_configured": settings.s3_endpoint_url is not None,
        "key_count": response.get("KeyCount", 0),
    }