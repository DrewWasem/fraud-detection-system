"""Scoring API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class AddressInput(BaseModel):
    """Address input model."""
    street: str
    city: str
    state: str
    zip: str


class SyntheticScoreRequest(BaseModel):
    """Request model for synthetic scoring."""
    ssn_last4: str
    ssn_first5: str
    dob: str
    first_name: str
    last_name: str
    address: AddressInput
    phone: str
    email: str
    application_date: str
    device_fingerprint: Optional[str] = None


class SyntheticScoreResponse(BaseModel):
    """Response model for synthetic scoring."""
    score: float
    risk_level: str
    signals: list[str]
    explanation: str


class BustOutRequest(BaseModel):
    """Request model for bust-out prediction."""
    account_id: str
    include_credit_behavior: bool = True


class BustOutResponse(BaseModel):
    """Response model for bust-out prediction."""
    probability: float
    risk_level: str
    days_to_bust_out: Optional[int]
    warning_signals: list[str]
    recommended_action: str


@router.post("/synthetic", response_model=SyntheticScoreResponse)
async def score_synthetic_identity(request: SyntheticScoreRequest):
    """Score an identity for synthetic fraud risk."""
    # TODO: Integrate with actual scoring pipeline
    return SyntheticScoreResponse(
        score=0.0,
        risk_level="minimal",
        signals=[],
        explanation="No significant risk factors detected",
    )


@router.post("/bust-out", response_model=BustOutResponse)
async def predict_bust_out(request: BustOutRequest):
    """Predict bust-out risk for an account."""
    # TODO: Integrate with bust-out predictor
    return BustOutResponse(
        probability=0.0,
        risk_level="minimal",
        days_to_bust_out=None,
        warning_signals=[],
        recommended_action="NO_ACTION",
    )


@router.post("/application")
async def score_application(request: SyntheticScoreRequest):
    """Full application scoring combining all models."""
    # TODO: Integrate with ensemble detector
    return {
        "application_id": "app_123",
        "synthetic_score": 0.0,
        "bust_out_risk": 0.0,
        "overall_risk": "minimal",
        "recommended_action": "APPROVE",
    }
