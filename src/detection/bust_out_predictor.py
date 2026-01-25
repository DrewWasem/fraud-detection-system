"""Bust-out fraud prediction model."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
import joblib

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BustOutPrediction:
    """Bust-out prediction result."""

    account_id: str
    identity_id: str
    bust_out_probability: float
    days_to_bust_out: Optional[int]
    risk_level: str
    warning_signals: list[str]
    recommended_action: str
    predicted_at: datetime


@dataclass
class CreditSequence:
    """Credit behavior sequence for an account."""

    account_id: str
    monthly_balances: list[float]
    monthly_payments: list[float]
    credit_limit_changes: list[float]
    utilization_rates: list[float]
    cash_advance_amounts: list[float]
    months_on_books: int


class BustOutPredictor:
    """Predicts imminent bust-out fraud."""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize predictor.

        Args:
            model_path: Path to trained model
        """
        self._settings = get_settings()
        self._model = None

        if model_path:
            self.load_model(model_path)

    def load_model(self, path: str) -> None:
        """Load trained model."""
        try:
            self._model = joblib.load(path)
            logger.info(f"Loaded bust-out model from {path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def predict(
        self,
        account_id: str,
        identity_id: str,
        credit_sequence: CreditSequence,
        synthetic_score: Optional[float] = None,
    ) -> BustOutPrediction:
        """
        Predict bust-out probability for an account.

        Args:
            account_id: Account to predict
            identity_id: Associated identity
            credit_sequence: Credit behavior sequence
            synthetic_score: Optional synthetic identity score

        Returns:
            BustOutPrediction with risk assessment
        """
        # Extract features from sequence
        features = self._extract_sequence_features(credit_sequence)

        # Add synthetic score if available
        if synthetic_score is not None:
            features["synthetic_score"] = synthetic_score

        # Calculate bust-out probability
        probability = self._calculate_probability(features)

        # Identify warning signals
        signals = self._identify_warning_signals(credit_sequence, features)

        # Estimate days to bust-out if high risk
        days_to_bust_out = None
        if probability > 0.5:
            days_to_bust_out = self._estimate_time_to_bust_out(
                credit_sequence, probability
            )

        # Determine risk level and action
        risk_level, recommended_action = self._determine_risk_action(
            probability, signals
        )

        return BustOutPrediction(
            account_id=account_id,
            identity_id=identity_id,
            bust_out_probability=probability,
            days_to_bust_out=days_to_bust_out,
            risk_level=risk_level,
            warning_signals=signals,
            recommended_action=recommended_action,
            predicted_at=datetime.now(),
        )

    def _extract_sequence_features(self, seq: CreditSequence) -> dict:
        """Extract ML features from credit sequence."""
        features = {}

        # Balance trends
        if len(seq.monthly_balances) >= 3:
            balances = np.array(seq.monthly_balances)
            features["balance_trend"] = np.polyfit(
                range(len(balances)), balances, 1
            )[0]
            features["balance_volatility"] = np.std(balances)
            features["max_balance"] = np.max(balances)
            features["recent_balance_increase"] = (
                balances[-1] - balances[-3] if len(balances) >= 3 else 0
            )

        # Payment behavior
        if len(seq.monthly_payments) >= 3:
            payments = np.array(seq.monthly_payments)
            features["avg_payment"] = np.mean(payments)
            features["payment_trend"] = np.polyfit(
                range(len(payments)), payments, 1
            )[0]
            features["min_payment_ratio"] = (
                np.min(payments) / np.max(payments) if np.max(payments) > 0 else 0
            )
            # Declining payments
            features["declining_payments"] = int(
                np.mean(payments[-3:]) < np.mean(payments[:-3]) * 0.8
                if len(payments) >= 6
                else False
            )

        # Utilization patterns
        if len(seq.utilization_rates) >= 3:
            utilization = np.array(seq.utilization_rates)
            features["avg_utilization"] = np.mean(utilization)
            features["max_utilization"] = np.max(utilization)
            features["utilization_trend"] = np.polyfit(
                range(len(utilization)), utilization, 1
            )[0]

        # Cash advances (strong bust-out indicator)
        if seq.cash_advance_amounts:
            cash = np.array(seq.cash_advance_amounts)
            features["total_cash_advances"] = np.sum(cash)
            features["cash_advance_frequency"] = np.sum(cash > 0)
            features["recent_cash_advances"] = (
                np.sum(cash[-3:]) if len(cash) >= 3 else np.sum(cash)
            )

        # Credit limit changes
        if seq.credit_limit_changes:
            limit_changes = np.array(seq.credit_limit_changes)
            features["total_limit_increases"] = np.sum(limit_changes[limit_changes > 0])
            features["recent_limit_increase"] = (
                limit_changes[-1] if len(limit_changes) > 0 else 0
            )

        # Account age
        features["months_on_books"] = seq.months_on_books

        return features

    def _calculate_probability(self, features: dict) -> float:
        """Calculate bust-out probability from features."""
        if self._model is not None:
            # Use trained model
            feature_vector = self._features_to_vector(features)
            return float(self._model.predict_proba([feature_vector])[0, 1])

        # Rule-based fallback
        probability = 0.0

        # High utilization trending up
        if features.get("utilization_trend", 0) > 0.05:
            probability += 0.2
        if features.get("max_utilization", 0) > 0.9:
            probability += 0.15

        # Declining payments
        if features.get("declining_payments"):
            probability += 0.25
        if features.get("payment_trend", 0) < -100:
            probability += 0.15

        # Cash advance activity
        if features.get("cash_advance_frequency", 0) > 2:
            probability += 0.2
        if features.get("recent_cash_advances", 0) > 1000:
            probability += 0.15

        # New account with rapid balance growth
        if features.get("months_on_books", 0) < 12:
            if features.get("balance_trend", 0) > 500:
                probability += 0.2

        # Synthetic identity indicator
        if features.get("synthetic_score", 0) > 0.7:
            probability += 0.3

        return min(1.0, probability)

    def _features_to_vector(self, features: dict) -> np.ndarray:
        """Convert feature dict to vector for model."""
        feature_names = [
            "balance_trend",
            "balance_volatility",
            "max_balance",
            "recent_balance_increase",
            "avg_payment",
            "payment_trend",
            "declining_payments",
            "avg_utilization",
            "max_utilization",
            "utilization_trend",
            "total_cash_advances",
            "cash_advance_frequency",
            "recent_cash_advances",
            "months_on_books",
            "synthetic_score",
        ]
        return np.array([features.get(name, 0.0) for name in feature_names])

    def _identify_warning_signals(
        self, seq: CreditSequence, features: dict
    ) -> list[str]:
        """Identify specific warning signals."""
        signals = []

        if features.get("max_utilization", 0) > 0.95:
            signals.append("MAXED_OUT")

        if features.get("declining_payments"):
            signals.append("DECLINING_PAYMENTS")

        if features.get("cash_advance_frequency", 0) >= 3:
            signals.append("FREQUENT_CASH_ADVANCES")

        if features.get("utilization_trend", 0) > 0.1:
            signals.append("RAPID_UTILIZATION_INCREASE")

        if features.get("balance_trend", 0) > 1000:
            signals.append("RAPID_BALANCE_GROWTH")

        if features.get("synthetic_score", 0) > 0.7:
            signals.append("HIGH_SYNTHETIC_RISK")

        return signals

    def _estimate_time_to_bust_out(
        self, seq: CreditSequence, probability: float
    ) -> int:
        """Estimate days until likely bust-out."""
        # Simple heuristic based on utilization trajectory
        if len(seq.utilization_rates) < 3:
            return 90

        current_util = seq.utilization_rates[-1]
        util_trend = np.mean(np.diff(seq.utilization_rates[-6:]))

        if current_util >= 0.95:
            return 30  # Already maxed
        elif util_trend > 0:
            # Estimate time to reach 100%
            remaining = 1.0 - current_util
            months_to_max = remaining / util_trend if util_trend > 0 else 6
            return int(min(90, max(7, months_to_max * 30)))
        else:
            return 90

    def _determine_risk_action(
        self, probability: float, signals: list[str]
    ) -> tuple[str, str]:
        """Determine risk level and recommended action."""
        threshold = self._settings.bust_out.threshold

        if probability >= 0.9:
            return "critical", "IMMEDIATE_REVIEW_CREDIT_FREEZE"
        elif probability >= threshold:
            return "high", "URGENT_REVIEW_REDUCE_LIMIT"
        elif probability >= 0.5:
            return "medium", "MONITOR_CLOSELY"
        elif probability >= 0.3:
            return "low", "STANDARD_MONITORING"
        else:
            return "minimal", "NO_ACTION"
