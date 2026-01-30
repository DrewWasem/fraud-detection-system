"""Scoring API endpoints."""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api import dependencies
from src.identity_elements.ssn.validator import SSNValidator
from src.identity_elements.ssn.issuance_checker import SSNIssuanceChecker

logger = logging.getLogger(__name__)
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
    velocity_score: Optional[float] = None
    graph_score: Optional[float] = None


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


class ApplicationScoreResponse(BaseModel):
    """Response model for full application scoring."""

    application_id: str
    identity_id: str
    synthetic_score: float
    bust_out_risk: float
    velocity_score: float
    overall_risk: str
    recommended_action: str
    signals: list[str]
    explanation: str


def _hash_value(value: str) -> str:
    """Create a hash of a value for privacy."""
    return hashlib.sha256(value.lower().strip().encode()).hexdigest()


def _normalize_address(address: AddressInput) -> str:
    """Normalize and hash an address."""
    normalized = f"{address.street}|{address.city}|{address.state}|{address.zip}"
    return _hash_value(normalized.lower().replace(" ", ""))


def _normalize_phone(phone: str) -> str:
    """Normalize and hash a phone number."""
    digits = "".join(c for c in phone if c.isdigit())
    return _hash_value(digits)


def _create_identity_id(ssn_first5: str, ssn_last4: str, first_name: str, last_name: str) -> str:
    """Create a unique identity ID."""
    identity_string = f"{ssn_first5}{ssn_last4}|{first_name}|{last_name}"
    return _hash_value(identity_string)[:16]


@router.post("/synthetic", response_model=SyntheticScoreResponse)
async def score_synthetic_identity(request: SyntheticScoreRequest):
    """
    Score an identity for synthetic fraud risk.

    Analyzes SSN validity, PII velocity, graph connections, and credit behavior
    to determine synthetic identity risk.
    """
    try:
        # Parse DOB
        try:
            dob = datetime.strptime(request.dob, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Create hashes for PII elements
        ssn_hash = _hash_value(f"{request.ssn_first5}{request.ssn_last4}")
        address_hash = _normalize_address(request.address)
        phone_hash = _normalize_phone(request.phone)
        email_hash = _hash_value(request.email)
        identity_id = _create_identity_id(
            request.ssn_first5, request.ssn_last4,
            request.first_name, request.last_name
        )
        name_hash = _hash_value(f"{request.first_name}|{request.last_name}")

        # Validate SSN
        ssn_validator = SSNValidator()
        ssn_signals = {}

        try:
            ssn_full = f"{request.ssn_first5}{request.ssn_last4}"
            ssn_validation = ssn_validator.validate(
                ssn_full, dob=dob, full_validation=True
            )
            ssn_signals = {
                "is_valid": ssn_validation.is_valid,
                "is_itin": ssn_validation.is_itin,
                "is_randomized_era": ssn_validation.is_randomized_era,
                "area_valid": ssn_validation.area_valid,
                "group_valid": ssn_validation.group_valid,
            }

            # Check issuance consistency
            issuance_checker = SSNIssuanceChecker()
            issuance_result = issuance_checker.check_ssn_dob_consistency(
                request.ssn_first5[:3], dob
            )
            ssn_signals["issuance_consistent"] = issuance_result.get("is_consistent", True)
            if not issuance_result.get("is_consistent", True):
                ssn_signals["issuance_issue"] = issuance_result.get("message", "")
        except Exception as e:
            logger.warning(f"SSN validation error: {e}")

        # Get velocity analysis
        velocity_analyzer = dependencies.get_velocity_analyzer()
        velocity_result = velocity_analyzer.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email_hash=email_hash,
            device_fingerprint=request.device_fingerprint,
        )

        # Record element usage for future velocity tracking
        velocity_analyzer.record_identity_elements(
            identity_hash=identity_id,
            ssn_hash=ssn_hash,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email_hash=email_hash,
            device_fingerprint=request.device_fingerprint,
        )

        # Get graph features if available
        graph_features = {}
        try:
            graph_extractor = dependencies.get_graph_feature_extractor()
            features = graph_extractor.extract_features(identity_id)
            graph_features = {
                "degree": features.degree,
                "cluster_size": features.cluster_size,
                "shared_ssn_count": features.shared_ssn_count,
                "shared_address_count": features.shared_address_count,
                "shared_phone_count": features.shared_phone_count,
                "neighbor_avg_synthetic_score": features.neighbor_avg_synthetic_score,
            }
        except Exception as e:
            logger.warning(f"Graph feature extraction failed: {e}")

        # Run ensemble detection
        ensemble = dependencies.get_ensemble_detector()
        result = ensemble.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            claimed_dob=dob,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email=request.email,
            device_fingerprint=request.device_fingerprint,
            ssn_signals=ssn_signals,
            graph_features=graph_features,
        )

        return SyntheticScoreResponse(
            score=result.final_risk_score,
            risk_level=result.final_risk_level,
            signals=result.all_signals,
            explanation=result.explanation,
            velocity_score=velocity_result.overall_velocity_score,
            graph_score=graph_features.get("neighbor_avg_synthetic_score"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring identity: {e}")
        raise HTTPException(status_code=500, detail="Error processing scoring request")


@router.post("/bust-out", response_model=BustOutResponse)
async def predict_bust_out(request: BustOutRequest):
    """
    Predict bust-out risk for an account.

    Analyzes credit behavior patterns to predict likelihood of bust-out fraud.
    """
    try:
        # Get bureau data for the account
        bureau = dependencies.get_bureau_connector()

        # For bust-out prediction, we need account history
        # For now, return a placeholder based on mock data
        # In production, this would look up the account and analyze behavior

        # Generate a deterministic result based on account_id
        account_hash = _hash_value(request.account_id)
        seed = int(account_hash[:8], 16)

        # Use seed to generate consistent results
        import random

        rng = random.Random(seed)

        probability = rng.uniform(0.0, 0.5)  # Most accounts low risk
        if rng.random() < 0.1:  # 10% elevated risk
            probability = rng.uniform(0.5, 0.9)

        if probability >= 0.75:
            risk_level = "critical"
            days_to_bust_out = rng.randint(15, 45)
            action = "IMMEDIATE_CREDIT_FREEZE"
        elif probability >= 0.5:
            risk_level = "high"
            days_to_bust_out = rng.randint(30, 90)
            action = "REDUCE_CREDIT_LIMIT"
        elif probability >= 0.25:
            risk_level = "medium"
            days_to_bust_out = rng.randint(60, 180)
            action = "ENHANCED_MONITORING"
        else:
            risk_level = "low"
            days_to_bust_out = None
            action = "STANDARD_MONITORING"

        warning_signals = []
        if probability > 0.3:
            possible_signals = [
                "RAPID_BALANCE_INCREASE",
                "CASH_ADVANCE_PATTERN",
                "PAYMENT_VELOCITY_DECLINE",
                "CREDIT_SEEKING_BEHAVIOR",
                "ADDRESS_INSTABILITY",
            ]
            num_signals = min(int(probability * 5), len(possible_signals))
            warning_signals = rng.sample(possible_signals, num_signals)

        return BustOutResponse(
            probability=round(probability, 3),
            risk_level=risk_level,
            days_to_bust_out=days_to_bust_out,
            warning_signals=warning_signals,
            recommended_action=action,
        )

    except Exception as e:
        logger.error(f"Error predicting bust-out: {e}")
        raise HTTPException(status_code=500, detail="Error processing bust-out prediction")


@router.post("/application", response_model=ApplicationScoreResponse)
async def score_application(request: SyntheticScoreRequest):
    """
    Full application scoring combining all models.

    This endpoint performs comprehensive analysis including:
    - SSN validation
    - Identity graph analysis
    - Velocity analysis
    - Credit behavior analysis
    - Bust-out prediction
    """
    try:
        # Parse DOB
        try:
            dob = datetime.strptime(request.dob, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Create hashes
        ssn_hash = _hash_value(f"{request.ssn_first5}{request.ssn_last4}")
        address_hash = _normalize_address(request.address)
        phone_hash = _normalize_phone(request.phone)
        email_hash = _hash_value(request.email)
        identity_id = _create_identity_id(
            request.ssn_first5, request.ssn_last4,
            request.first_name, request.last_name
        )
        name_hash = _hash_value(f"{request.first_name}|{request.last_name}")

        # Generate application ID
        app_date = request.application_date or datetime.now().isoformat()
        application_id = f"APP-{_hash_value(identity_id + app_date)[:8].upper()}"

        # Add identity to graph
        try:
            identity_graph = dependencies.get_identity_graph()
            identity_graph.add_identity(
                identity_id=identity_id,
                ssn_hash=ssn_hash,
                name_hash=name_hash,
                dob=dob,
                address_hash=address_hash,
                phone_hash=phone_hash,
                email_hash=email_hash,
                device_fingerprint=request.device_fingerprint,
            )
        except Exception as e:
            logger.warning(f"Failed to add identity to graph: {e}")

        # Record velocity metrics
        velocity_analyzer = dependencies.get_velocity_analyzer()
        velocity_analyzer.record_identity_elements(
            identity_hash=identity_id,
            ssn_hash=ssn_hash,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email_hash=email_hash,
            device_fingerprint=request.device_fingerprint,
        )

        # Get velocity analysis
        velocity_result = velocity_analyzer.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email_hash=email_hash,
            device_fingerprint=request.device_fingerprint,
        )

        # Get graph features
        graph_features = {}
        try:
            graph_extractor = dependencies.get_graph_feature_extractor()
            features = graph_extractor.extract_features(identity_id)
            graph_features = {
                "degree": features.degree,
                "cluster_size": features.cluster_size,
                "shared_ssn_count": features.shared_ssn_count,
                "shared_address_count": features.shared_address_count,
                "shared_phone_count": features.shared_phone_count,
                "neighbor_avg_synthetic_score": features.neighbor_avg_synthetic_score,
            }
        except Exception as e:
            logger.warning(f"Graph feature extraction failed: {e}")

        # Run full ensemble analysis
        ensemble = dependencies.get_ensemble_detector()
        result = ensemble.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            claimed_dob=dob,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email=request.email,
            device_fingerprint=request.device_fingerprint,
            graph_features=graph_features,
        )

        # Update synthetic score in graph
        try:
            identity_graph = dependencies.get_identity_graph()
            identity_graph.update_synthetic_score(identity_id, result.final_risk_score)
        except Exception as e:
            logger.warning(f"Failed to update synthetic score: {e}")

        # Determine bust-out risk (simplified for application scoring)
        bust_out_risk = 0.0
        if result.bust_out_prediction:
            bust_out_risk = result.bust_out_prediction.bust_out_probability

        return ApplicationScoreResponse(
            application_id=application_id,
            identity_id=identity_id,
            synthetic_score=result.final_risk_score,
            bust_out_risk=bust_out_risk,
            velocity_score=velocity_result.overall_velocity_score,
            overall_risk=result.final_risk_level,
            recommended_action=result.recommended_action,
            signals=result.all_signals,
            explanation=result.explanation,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring application: {e}")
        raise HTTPException(status_code=500, detail="Error processing application")


@router.get("/signals/{identity_id}")
async def get_identity_signals(identity_id: str):
    """Get all triggered signals for an identity."""
    # This would look up historical signals for the identity
    # For now, return empty signals
    return {
        "identity_id": identity_id,
        "signals": [],
        "last_scored": None,
        "score_history": [],
    }
