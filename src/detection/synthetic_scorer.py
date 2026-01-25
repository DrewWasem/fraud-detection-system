"""Synthetic identity scoring model."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import joblib

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SyntheticScore:
    """Synthetic identity score result."""

    identity_id: str
    score: float  # 0-1, higher = more likely synthetic
    risk_level: str  # low, medium, high, critical
    component_scores: dict
    triggered_signals: list[str]
    explanation: str
    scored_at: datetime


class SyntheticScorer:
    """Scores identities for synthetic fraud risk."""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize scorer.

        Args:
            model_path: Path to trained model
        """
        self._settings = get_settings()
        self._model = None
        self._model_path = model_path

        if model_path:
            self.load_model(model_path)

    def load_model(self, path: str) -> None:
        """Load trained model from disk."""
        try:
            self._model = joblib.load(path)
            logger.info(f"Loaded synthetic scorer model from {path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def score(
        self,
        identity_id: str,
        ssn_signals: dict,
        graph_features: dict,
        velocity_signals: dict,
        credit_behavior: dict,
        device_signals: dict,
    ) -> SyntheticScore:
        """
        Score an identity for synthetic fraud risk.

        Args:
            identity_id: Identity to score
            ssn_signals: SSN-related signals
            graph_features: Graph-based features
            velocity_signals: PII velocity signals
            credit_behavior: Credit behavior signals
            device_signals: Device binding signals

        Returns:
            SyntheticScore with risk assessment
        """
        weights = self._settings.scoring

        # Calculate component scores
        ssn_score = self._score_ssn_signals(ssn_signals)
        graph_score = self._score_graph_features(graph_features)
        velocity_score = self._score_velocity(velocity_signals)
        credit_score = self._score_credit_behavior(credit_behavior)
        device_score = self._score_device(device_signals)

        component_scores = {
            "ssn": ssn_score,
            "graph": graph_score,
            "velocity": velocity_score,
            "credit": credit_score,
            "device": device_score,
        }

        # Weighted combination
        final_score = (
            ssn_score * weights.ssn_signals_weight
            + graph_score * weights.graph_features_weight
            + velocity_score * weights.velocity_signals_weight
            + credit_score * weights.credit_behavior_weight
            + device_score * weights.device_binding_weight
        )

        # Collect triggered signals
        triggered = self._get_triggered_signals(
            ssn_signals, graph_features, velocity_signals, credit_behavior, device_signals
        )

        # Determine risk level
        if final_score >= weights.high_risk_threshold:
            risk_level = "critical" if final_score >= 0.9 else "high"
        elif final_score >= weights.medium_risk_threshold:
            risk_level = "medium"
        elif final_score >= weights.review_threshold:
            risk_level = "low"
        else:
            risk_level = "minimal"

        # Generate explanation
        explanation = self._generate_explanation(
            component_scores, triggered, risk_level
        )

        return SyntheticScore(
            identity_id=identity_id,
            score=final_score,
            risk_level=risk_level,
            component_scores=component_scores,
            triggered_signals=triggered,
            explanation=explanation,
            scored_at=datetime.now(),
        )

    def _score_ssn_signals(self, signals: dict) -> float:
        """Score SSN-related signals."""
        score = 0.0

        # SSN-DOB mismatch
        if signals.get("ssn_dob_mismatch"):
            score += 0.6

        # Death Master File match
        if signals.get("death_master_match"):
            score += 0.8

        # Invalid SSN
        if signals.get("invalid_ssn"):
            score += 0.5

        # ITIN used as SSN
        if signals.get("itin_as_ssn"):
            score += 0.4

        # Multiple SSNs for same name
        if signals.get("multiple_ssns"):
            score += 0.5

        return min(1.0, score)

    def _score_graph_features(self, features: dict) -> float:
        """Score graph-based features."""
        score = 0.0

        # Shared SSN with others (very suspicious)
        shared_ssn = features.get("shared_ssn_count", 0)
        if shared_ssn > 0:
            score += min(0.6, shared_ssn * 0.3)

        # High cluster density
        if features.get("cluster_density", 0) > 0.5:
            score += 0.2

        # Large cluster size
        cluster_size = features.get("cluster_size", 1)
        if cluster_size > 5:
            score += min(0.3, (cluster_size - 5) * 0.05)

        # High neighbor synthetic scores
        if features.get("neighbor_avg_synthetic_score", 0) > 0.5:
            score += 0.2

        return min(1.0, score)

    def _score_velocity(self, signals: dict) -> float:
        """Score velocity signals."""
        score = 0.0

        # Address velocity
        addr_velocity = signals.get("address_velocity_score", 0)
        score += addr_velocity * 0.3

        # Phone velocity
        phone_velocity = signals.get("phone_velocity_score", 0)
        score += phone_velocity * 0.4

        # Email velocity
        email_velocity = signals.get("email_velocity_score", 0)
        score += email_velocity * 0.3

        return min(1.0, score)

    def _score_credit_behavior(self, signals: dict) -> float:
        """Score credit behavior signals."""
        score = 0.0

        # Thin file
        if signals.get("is_thin_file"):
            score += 0.2

        # Credit file younger than claimed age
        if signals.get("file_age_mismatch"):
            score += 0.4

        # Rapid credit building
        if signals.get("rapid_credit_building"):
            score += 0.3

        # AU abuse pattern
        if signals.get("au_abuse_pattern"):
            score += 0.5

        return min(1.0, score)

    def _score_device(self, signals: dict) -> float:
        """Score device signals."""
        score = 0.0

        # Weak device binding
        if signals.get("weak_binding", False):
            score += 0.3

        # Device shared with many identities
        if signals.get("shared_device_count", 0) > 3:
            score += 0.4

        # Known fraud device
        if signals.get("known_fraud_device"):
            score += 0.8

        # Emulator/VM detected
        if signals.get("emulator_detected"):
            score += 0.5

        return min(1.0, score)

    def _get_triggered_signals(
        self,
        ssn_signals: dict,
        graph_features: dict,
        velocity_signals: dict,
        credit_behavior: dict,
        device_signals: dict,
    ) -> list[str]:
        """Collect list of triggered signals."""
        triggered = []

        # SSN signals
        if ssn_signals.get("ssn_dob_mismatch"):
            triggered.append("SSN_DOB_MISMATCH")
        if ssn_signals.get("death_master_match"):
            triggered.append("DEATH_MASTER_MATCH")
        if ssn_signals.get("multiple_ssns"):
            triggered.append("MULTIPLE_SSNS")

        # Graph signals
        if graph_features.get("shared_ssn_count", 0) > 0:
            triggered.append("SHARED_SSN")
        if graph_features.get("cluster_size", 1) > 5:
            triggered.append("LARGE_CLUSTER")

        # Velocity signals
        if velocity_signals.get("address_velocity_score", 0) > 0.5:
            triggered.append("HIGH_ADDRESS_VELOCITY")
        if velocity_signals.get("phone_velocity_score", 0) > 0.5:
            triggered.append("HIGH_PHONE_VELOCITY")

        # Credit signals
        if credit_behavior.get("is_thin_file"):
            triggered.append("THIN_FILE")
        if credit_behavior.get("au_abuse_pattern"):
            triggered.append("AU_ABUSE")

        # Device signals
        if device_signals.get("known_fraud_device"):
            triggered.append("FRAUD_DEVICE")

        return triggered

    def _generate_explanation(
        self,
        component_scores: dict,
        triggered: list[str],
        risk_level: str,
    ) -> str:
        """Generate human-readable explanation."""
        if risk_level == "minimal":
            return "No significant synthetic identity indicators detected."

        parts = [f"Risk level: {risk_level.upper()}."]

        # Highlight top contributing factors
        sorted_components = sorted(
            component_scores.items(), key=lambda x: x[1], reverse=True
        )
        top_component = sorted_components[0]
        if top_component[1] > 0.3:
            parts.append(
                f"Primary risk factor: {top_component[0]} signals "
                f"(score: {top_component[1]:.2f})."
            )

        if triggered:
            parts.append(f"Triggered signals: {', '.join(triggered[:5])}.")

        return " ".join(parts)

    def batch_score(
        self, identities: list[dict]
    ) -> list[SyntheticScore]:
        """Score multiple identities."""
        return [
            self.score(
                identity_id=ident.get("identity_id", ""),
                ssn_signals=ident.get("ssn_signals", {}),
                graph_features=ident.get("graph_features", {}),
                velocity_signals=ident.get("velocity_signals", {}),
                credit_behavior=ident.get("credit_behavior", {}),
                device_signals=ident.get("device_signals", {}),
            )
            for ident in identities
        ]
