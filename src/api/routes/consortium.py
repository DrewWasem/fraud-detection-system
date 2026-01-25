"""Consortium data sharing API endpoints."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ShareSyntheticRequest(BaseModel):
    """Request model for sharing synthetic identity."""
    identity_hash: str
    ssn_hash: str
    confidence_score: float
    detection_details: dict


class ShareBustOutRequest(BaseModel):
    """Request model for sharing bust-out."""
    identity_hash: str
    account_id: str
    amount: float
    detection_details: dict


@router.post("/share/synthetic")
async def share_synthetic_identity(request: ShareSyntheticRequest):
    """Share confirmed synthetic identity with consortium."""
    return {
        "report_id": "CR-NEW",
        "status": "submitted",
    }


@router.post("/share/bust-out")
async def share_bust_out(request: ShareBustOutRequest):
    """Share confirmed bust-out with consortium."""
    return {
        "report_id": "CR-NEW",
        "status": "submitted",
    }


@router.get("/query")
async def query_consortium(
    identity_hash: Optional[str] = None,
    ssn_hash: Optional[str] = None,
):
    """Query consortium for existing reports."""
    return {
        "reports": [],
        "total_count": 0,
    }


@router.get("/alerts")
async def get_consortium_alerts(
    limit: int = 50,
    alert_type: Optional[str] = None,
):
    """Get recent consortium alerts."""
    return {
        "alerts": [],
        "total_count": 0,
    }
