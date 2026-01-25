"""Bust-out event tracking and analysis."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BustOutEvent:
    """Recorded bust-out event."""
    event_id: str
    account_id: str
    identity_id: str
    prediction_date: Optional[datetime]
    bust_out_date: datetime
    amount_lost: float
    was_predicted: bool
    prediction_lead_days: Optional[int]


class BustOutTracker:
    """Tracks bust-out events for model validation."""

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._events: list[BustOutEvent] = []
        self._predictions: dict[str, dict] = {}

    def record_prediction(
        self,
        account_id: str,
        identity_id: str,
        probability: float,
        predicted_days: Optional[int],
        timestamp: Optional[datetime] = None,
    ):
        """Record a bust-out prediction."""
        self._predictions[account_id] = {
            "identity_id": identity_id,
            "probability": probability,
            "predicted_days": predicted_days,
            "timestamp": timestamp or datetime.now(),
        }

    def record_bust_out(
        self,
        account_id: str,
        identity_id: str,
        amount_lost: float,
        bust_out_date: Optional[datetime] = None,
    ):
        """Record an actual bust-out event."""
        import uuid

        bust_out_date = bust_out_date or datetime.now()
        prediction = self._predictions.get(account_id)

        was_predicted = False
        prediction_date = None
        lead_days = None

        if prediction:
            was_predicted = prediction["probability"] > 0.5
            prediction_date = prediction["timestamp"]
            lead_days = (bust_out_date - prediction_date).days

        event = BustOutEvent(
            event_id=f"BO-{uuid.uuid4().hex[:8].upper()}",
            account_id=account_id,
            identity_id=identity_id,
            prediction_date=prediction_date,
            bust_out_date=bust_out_date,
            amount_lost=amount_lost,
            was_predicted=was_predicted,
            prediction_lead_days=lead_days,
        )

        self._events.append(event)
        logger.info(f"Recorded bust-out event: {event.event_id}")
        return event

    def get_detection_rate(self, period_days: int = 90) -> dict:
        """Calculate bust-out detection rate."""
        cutoff = datetime.now() - timedelta(days=period_days)
        recent_events = [e for e in self._events if e.bust_out_date >= cutoff]

        if not recent_events:
            return {
                "detection_rate": 0.0,
                "total_events": 0,
                "detected_events": 0,
                "avg_lead_days": None,
                "total_loss": 0.0,
                "prevented_loss": 0.0,
            }

        detected = [e for e in recent_events if e.was_predicted]
        lead_days = [e.prediction_lead_days for e in detected if e.prediction_lead_days]

        return {
            "detection_rate": len(detected) / len(recent_events),
            "total_events": len(recent_events),
            "detected_events": len(detected),
            "avg_lead_days": sum(lead_days) / len(lead_days) if lead_days else None,
            "total_loss": sum(e.amount_lost for e in recent_events),
            "prevented_loss": sum(e.amount_lost for e in detected),
        }

    def get_events(
        self,
        period_days: Optional[int] = None,
        identity_id: Optional[str] = None,
    ) -> list[BustOutEvent]:
        """Get bust-out events with optional filters."""
        events = self._events

        if period_days:
            cutoff = datetime.now() - timedelta(days=period_days)
            events = [e for e in events if e.bust_out_date >= cutoff]

        if identity_id:
            events = [e for e in events if e.identity_id == identity_id]

        return sorted(events, key=lambda e: e.bust_out_date, reverse=True)
