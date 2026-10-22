"""
Common response envelope models shared across all endpoints.
Matches API_CONTRACT_DRAFT.md Section 1.
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Metadata block included in every API response."""

    snapshot_id: str = Field(..., examples=["2026.10.0-wia-demo"])
    mode: str = Field(..., examples=["DEMO"])
    boundary_version: Optional[str] = None
    total_count: Optional[int] = None
    data_origin: Optional[str] = Field(None, description="bmkg_live | bmkg_cache | fixture")
    last_success_at: Optional[str] = Field(None, description="ISO 8601 timestamp of last successful upstream fetch")
    is_stale: Optional[bool] = Field(None, description="True if data is beyond cache TTL or upstream is unavailable")


class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.

    Type-parameterised so each endpoint can declare a concrete ``data``
    schema, giving clients accurate OpenAPI documentation.

    Example::

        ApiResponse[list[RegionSummary]]
        ApiResponse[RegionDetail]
        ApiResponse[CompositeQueryResult]
    """

    status: str = "success"
    meta: ResponseMeta
    data: T


class ErrorDetail(BaseModel):
    """Error response body."""

    status: str = "error"
    code: str
    message: str
    detail: Optional[str] = None


class LiveUnavailableError(BaseModel):
    """
    503 response returned when ``mode=live`` (or ``X-Data-Mode: LIVE``) is
    requested but LIVE data sources are not yet connected.

    Headers set alongside this body:
    - ``X-NusaMatra-Mode: LIVE``
    - ``X-Data-Fallback: UNAVAILABLE``
    """

    status: str = "error"
    code: str = "LIVE_UNAVAILABLE"
    message: str = (
        "LIVE mode is not yet available. "
        "LIVE data sources have not been verified and connected. "
        "Use mode=demo for the demonstration dataset."
    )


class WeightValidationError(BaseModel):
    """
    422 response returned when composite-query weights are invalid.

    Common causes:
    - Sum of all weight values ≠ 10000 (basis points).
    - An ``indicator_id`` key is not recognised.
    """

    status: str = "error"
    code: str = "WEIGHT_VALIDATION_ERROR"
    message: str
    detail: Optional[str] = None
