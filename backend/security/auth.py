"""
Backend Authentication and Tenant Scoping
"""
import os
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from shared.constants import DEFAULT_API_KEY, DEFAULT_TENANT_ID

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_collector_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Validates X-API-Key on collector ingress endpoints.
    Returns tenant_id.
    """
    configured_key = os.getenv("COLLECTOR_API_KEY", DEFAULT_API_KEY)
    if not api_key or api_key != configured_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-API-Key header"
        )
    return os.getenv("TENANT_ID", DEFAULT_TENANT_ID)
