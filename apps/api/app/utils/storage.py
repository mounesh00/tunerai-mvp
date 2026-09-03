"""Storage utilities: filename sanitization, content hashing."""

import hashlib
import re
from pathlib import Path


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename for safe storage.

    - Remove path separators
    - Allow only alphanumeric, dash, underscore, dot
    - Enforce max length
    - Prevent empty names

    Args:
        filename: User-provided filename
        max_length: Maximum allowed length

    Returns:
        Safe, sanitized filename suitable for storage
    """
    if not filename:
        return "file"

    # Remove directory separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Keep only safe characters: alphanumeric, dash, underscore, dot
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)

    # Remove leading/trailing dots/dashes (prevent .bashrc, -.malicious)
    safe = safe.strip("._-")

    # Enforce max length
    if len(safe) > max_length:
        name, ext = safe.rsplit(".", 1) if "." in safe else (safe, "")
        max_name_len = max_length - len(ext) - 1 if ext else max_length
        safe = name[:max_name_len]
        if ext:
            safe = f"{safe}.{ext}"

    # Ensure not empty
    return safe or "file"


def calculate_content_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Calculate cryptographic hash of content.

    Args:
        content: File content bytes
        algorithm: Hash algorithm ("sha256" default)

    Returns:
        Hex digest of content hash
    """
    if algorithm == "sha256":
        return hashlib.sha256(content).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(content).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def generate_safe_object_key(
    organization_id: str,
    project_id: str,
    dataset_id: str,
    version_label: str,
    original_filename: str,
) -> str:
    """
    Generate safe S3/R2 object key.

    Server-side generation prevents path traversal/injection attacks.

    Args:
        organization_id: UUID
        project_id: UUID
        dataset_id: UUID
        version_label: e.g. "v1"
        original_filename: User-provided filename (will be sanitized)

    Returns:
        Safe S3 object key: organizations/{org}/projects/{proj}/datasets/{ds}/versions/{ver}/{sanitized}
    """
    sanitized = sanitize_filename(original_filename)
    return f"organizations/{organization_id}/projects/{project_id}/datasets/{dataset_id}/versions/{version_label}/{sanitized}"
