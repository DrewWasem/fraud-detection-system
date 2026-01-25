"""Model performance monitoring."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Model performance metrics."""
    model_name: str
    period_start: datetime
    period_end: datetime
    total_predictions: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    auc_roc: Optional[float]


class ModelMonitor:
    """Monitors model performance over time."""

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._predictions: list[dict] = []
        self._outcomes: dict[str, bool] = {}

    def record_prediction(
        self,
        prediction_id: str,
        model_name: str,
        score: float,
        predicted_class: bool,
        timestamp: Optional[datetime] = None,
    ):
        """Record a model prediction."""
        self._predictions.append({
            "prediction_id": prediction_id,
            "model_name": model_name,
            "score": score,
            "predicted_class": predicted_class,
            "timestamp": timestamp or datetime.now(),
        })

    def record_outcome(
        self,
        prediction_id: str,
        actual_class: bool,
        outcome_date: Optional[datetime] = None,
    ):
        """Record actual outcome for a prediction."""
        self._outcomes[prediction_id] = actual_class

    def calculate_metrics(
        self,
        model_name: str,
        period_days: int = 30,
    ) -> PerformanceMetrics:
        """Calculate performance metrics for a model."""
        now = datetime.now()
        period_start = now - timedelta(days=period_days)

        # Filter predictions for period and model
        relevant_predictions = [
            p for p in self._predictions
            if p["model_name"] == model_name
            and p["timestamp"] >= period_start
            and p["prediction_id"] in self._outcomes
        ]

        # Calculate confusion matrix
        tp = fp = tn = fn = 0
        for pred in relevant_predictions:
            predicted = pred["predicted_class"]
            actual = self._outcomes[pred["prediction_id"]]

            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
            elif not predicted and not actual:
                tn += 1
            else:
                fn += 1

        # Calculate metrics
        total = tp + fp + tn + fn
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return PerformanceMetrics(
            model_name=model_name,
            period_start=period_start,
            period_end=now,
            total_predictions=total,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            auc_roc=None,  # Would need probability scores
        )

    def check_drift(
        self,
        model_name: str,
        threshold: float = 0.1,
    ) -> dict:
        """Check for model performance drift."""
        current = self.calculate_metrics(model_name, period_days=7)
        baseline = self.calculate_metrics(model_name, period_days=90)

        drift_detected = False
        drift_details = []

        if abs(current.precision - baseline.precision) > threshold:
            drift_detected = True
            drift_details.append(f"Precision drift: {baseline.precision:.2f} -> {current.precision:.2f}")

        if abs(current.recall - baseline.recall) > threshold:
            drift_detected = True
            drift_details.append(f"Recall drift: {baseline.recall:.2f} -> {current.recall:.2f}")

        return {
            "drift_detected": drift_detected,
            "details": drift_details,
            "current_metrics": current,
            "baseline_metrics": baseline,
        }
