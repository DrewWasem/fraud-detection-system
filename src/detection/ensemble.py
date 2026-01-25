"""Ensemble detection combining multiple models."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .synthetic_scorer import SyntheticScorer, SyntheticScore
from .bust_out_predictor import BustOutPredictor, BustOutPrediction, CreditSequence
from .velocity_analyzer import VelocityAnalyzer, VelocityAnalysis
from .credit_behavior import CreditBehaviorAnalyzer, CreditBehaviorAnalysis
from .authorized_user import AuthorizedUserDetector, AUAbuseAnalysis

logger = logging.getLogger(__name__)


@dataclass
class EnsembleResult:
    """Combined detection result from all models."""

    identity_id: str
    final_risk_score: float
    final_risk_level: str
    synthetic_score: Optional[SyntheticScore]
    bust_out_prediction: Optional[BustOutPrediction]
    velocity_analysis: Optional[VelocityAnalysis]
    credit_behavior: Optional[CreditBehaviorAnalysis]
    au_analysis: Optional[AUAbuseAnalysis]
    all_signals: list[str]
    recommended_action: str
    explanation: str
    analyzed_at: datetime


class EnsembleDetector:
    """Combines multiple detection models for comprehensive fraud detection."""

    def __init__(
        self,
        synthetic_scorer: Optional[SyntheticScorer] = None,
        bust_out_predictor: Optional[BustOutPredictor] = None,
        velocity_analyzer: Optional[VelocityAnalyzer] = None,
        credit_behavior_analyzer: Optional[CreditBehaviorAnalyzer] = None,
        au_detector: Optional[AuthorizedUserDetector] = None,
    ):
        """
        Initialize ensemble detector.

        Args:
            synthetic_scorer: Synthetic identity scorer
            bust_out_predictor: Bust-out predictor
            velocity_analyzer: Velocity analyzer
            credit_behavior_analyzer: Credit behavior analyzer
            au_detector: Authorized user detector
        """
        self.synthetic_scorer = synthetic_scorer or SyntheticScorer()
        self.bust_out_predictor = bust_out_predictor or BustOutPredictor()
        self.velocity_analyzer = velocity_analyzer or VelocityAnalyzer()
        self.credit_behavior_analyzer = (
            credit_behavior_analyzer or CreditBehaviorAnalyzer()
        )
        self.au_detector = au_detector or AuthorizedUserDetector()

    def analyze(
        self,
        identity_id: str,
        ssn_hash: str,
        claimed_dob: datetime,
        address_hash: str,
        phone_hash: str,
        email: str,
        device_fingerprint: Optional[str] = None,
        account_id: Optional[str] = None,
        credit_sequence: Optional[CreditSequence] = None,
        ssn_signals: Optional[dict] = None,
        graph_features: Optional[dict] = None,
    ) -> EnsembleResult:
        """
        Run full ensemble analysis on an identity.

        Args:
            identity_id: Identity to analyze
            ssn_hash: Hashed SSN
            claimed_dob: Claimed date of birth
            address_hash: Normalized address hash
            phone_hash: Hashed phone
            email: Email address
            device_fingerprint: Optional device fingerprint
            account_id: Optional account ID for bust-out analysis
            credit_sequence: Optional credit sequence for bust-out
            ssn_signals: Pre-computed SSN signals
            graph_features: Pre-computed graph features

        Returns:
            EnsembleResult with comprehensive analysis
        """
        all_signals = []

        # 1. Velocity Analysis
        velocity_result = self.velocity_analyzer.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            address_hash=address_hash,
            phone_hash=phone_hash,
            email_hash=email,
            device_fingerprint=device_fingerprint,
        )
        all_signals.extend(velocity_result.anomalies)

        # 2. Credit Behavior Analysis
        credit_result = self.credit_behavior_analyzer.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            claimed_dob=claimed_dob,
        )
        all_signals.extend(credit_result.anomalies)

        # 3. Authorized User Analysis
        au_result = self.au_detector.analyze(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
        )
        all_signals.extend(au_result.abuse_indicators)

        # 4. Synthetic Identity Scoring
        velocity_signals = {
            "address_velocity_score": velocity_result.address_velocity,
            "phone_velocity_score": velocity_result.phone_velocity,
            "email_velocity_score": velocity_result.email_velocity,
        }
        credit_signals = {
            "is_thin_file": credit_result.is_thin_file,
            "file_age_mismatch": "FILE_AGE_MISMATCH" in credit_result.anomalies,
            "rapid_credit_building": "RAPID_CREDIT_BUILDING" in credit_result.anomalies,
            "au_abuse_pattern": au_result.abuse_probability > 0.5,
        }
        device_signals = {
            "weak_binding": device_fingerprint is None,
        }

        synthetic_result = self.synthetic_scorer.score(
            identity_id=identity_id,
            ssn_signals=ssn_signals or {},
            graph_features=graph_features or {},
            velocity_signals=velocity_signals,
            credit_behavior=credit_signals,
            device_signals=device_signals,
        )
        all_signals.extend(synthetic_result.triggered_signals)

        # 5. Bust-out Prediction (if applicable)
        bust_out_result = None
        if account_id and credit_sequence:
            bust_out_result = self.bust_out_predictor.predict(
                account_id=account_id,
                identity_id=identity_id,
                credit_sequence=credit_sequence,
                synthetic_score=synthetic_result.score,
            )
            all_signals.extend(bust_out_result.warning_signals)

        # Combine scores
        final_score = self._calculate_final_score(
            synthetic_result,
            bust_out_result,
            velocity_result,
            credit_result,
            au_result,
        )

        # Determine final risk level
        final_risk_level = self._determine_final_risk_level(
            final_score, all_signals
        )

        # Generate recommended action
        recommended_action = self._get_recommended_action(
            final_risk_level, all_signals, bust_out_result
        )

        # Generate explanation
        explanation = self._generate_explanation(
            synthetic_result,
            bust_out_result,
            velocity_result,
            credit_result,
            au_result,
            final_risk_level,
        )

        return EnsembleResult(
            identity_id=identity_id,
            final_risk_score=final_score,
            final_risk_level=final_risk_level,
            synthetic_score=synthetic_result,
            bust_out_prediction=bust_out_result,
            velocity_analysis=velocity_result,
            credit_behavior=credit_result,
            au_analysis=au_result,
            all_signals=list(set(all_signals)),  # Deduplicate
            recommended_action=recommended_action,
            explanation=explanation,
            analyzed_at=datetime.now(),
        )

    def _calculate_final_score(
        self,
        synthetic: SyntheticScore,
        bust_out: Optional[BustOutPrediction],
        velocity: VelocityAnalysis,
        credit: CreditBehaviorAnalysis,
        au: AUAbuseAnalysis,
    ) -> float:
        """Calculate final combined risk score."""
        # Weighted combination
        weights = {
            "synthetic": 0.40,
            "velocity": 0.20,
            "credit": 0.15,
            "au": 0.15,
            "bust_out": 0.10,
        }

        score = (
            synthetic.score * weights["synthetic"]
            + velocity.overall_velocity_score * weights["velocity"]
            + credit.behavior_score * weights["credit"]
            + au.abuse_probability * weights["au"]
        )

        if bust_out:
            score += bust_out.bust_out_probability * weights["bust_out"]
        else:
            # Redistribute bust-out weight
            score = score / 0.9

        return min(1.0, score)

    def _determine_final_risk_level(
        self, score: float, signals: list[str]
    ) -> str:
        """Determine final risk level."""
        # Critical signals override score
        critical_signals = {
            "SSN_DOB_MISMATCH",
            "DEATH_MASTER_MATCH",
            "SHARED_SSN",
            "FRAUD_DEVICE",
        }

        if any(s in critical_signals for s in signals):
            return "critical"

        if score >= 0.85:
            return "critical"
        elif score >= 0.65:
            return "high"
        elif score >= 0.45:
            return "medium"
        elif score >= 0.25:
            return "low"
        else:
            return "minimal"

    def _get_recommended_action(
        self,
        risk_level: str,
        signals: list[str],
        bust_out: Optional[BustOutPrediction],
    ) -> str:
        """Get recommended action based on analysis."""
        if risk_level == "critical":
            if bust_out and bust_out.bust_out_probability > 0.8:
                return "IMMEDIATE_CREDIT_FREEZE_SAR_FILING"
            return "IMMEDIATE_REVIEW_DECLINE_APPLICATION"

        if risk_level == "high":
            return "MANUAL_REVIEW_REQUIRED"

        if risk_level == "medium":
            return "ENHANCED_VERIFICATION"

        if risk_level == "low":
            return "STANDARD_PROCESSING_MONITOR"

        return "APPROVE"

    def _generate_explanation(
        self,
        synthetic: SyntheticScore,
        bust_out: Optional[BustOutPrediction],
        velocity: VelocityAnalysis,
        credit: CreditBehaviorAnalysis,
        au: AUAbuseAnalysis,
        risk_level: str,
    ) -> str:
        """Generate human-readable explanation."""
        parts = [f"Overall risk: {risk_level.upper()}."]

        if synthetic.score > 0.5:
            parts.append(
                f"High synthetic identity risk ({synthetic.score:.0%}). "
                f"{synthetic.explanation}"
            )

        if bust_out and bust_out.bust_out_probability > 0.5:
            parts.append(
                f"Elevated bust-out risk ({bust_out.bust_out_probability:.0%}). "
                f"Estimated {bust_out.days_to_bust_out} days to potential bust-out."
            )

        if velocity.overall_velocity_score > 0.5:
            parts.append(
                f"High PII velocity detected. "
                f"Anomalies: {', '.join(velocity.anomalies)}."
            )

        if au.abuse_probability > 0.5:
            parts.append(
                f"Authorized user abuse pattern detected. "
                f"{au.au_account_count} AU accounts, "
                f"{au.unrelated_au_count} unrelated."
            )

        return " ".join(parts)

    def batch_analyze(
        self, identities: list[dict]
    ) -> list[EnsembleResult]:
        """Analyze multiple identities."""
        results = []
        for ident in identities:
            result = self.analyze(
                identity_id=ident["identity_id"],
                ssn_hash=ident["ssn_hash"],
                claimed_dob=ident["dob"],
                address_hash=ident["address_hash"],
                phone_hash=ident["phone_hash"],
                email=ident["email"],
                device_fingerprint=ident.get("device_fingerprint"),
                account_id=ident.get("account_id"),
                credit_sequence=ident.get("credit_sequence"),
                ssn_signals=ident.get("ssn_signals"),
                graph_features=ident.get("graph_features"),
            )
            results.append(result)
        return results
