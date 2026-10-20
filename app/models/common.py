"""
Common response envelope models shared across all endpoints.
Matches API_CONTRACT_DRAFT.md Section 1.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    """Metadata block included in every API response."""

    snapshot_id: str = Field(..., examples=["2026.10.0-wia-demo"])
    mode: str = Field(..., examples=["DEMO"])
    boundary_version: Optional[str] = None
    total_count: Optional[int] = None


class ApiResponse(BaseModel):
    """Standard API response envelope."""

    status: str = "success"
    meta: ResponseMeta
    data: Any


class ErrorDetail(BaseModel):
    """Error response body."""

    status: str = "error"
    code: str
    message: str
    detail: Optional[str] = None
