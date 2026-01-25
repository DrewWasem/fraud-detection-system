"""Industry consortium data receiver for shared fraud intelligence."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from kafka import KafkaConsumer

from src.config import get_settings

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Consortium alert types."""

    SYNTHETIC_IDENTITY = "synthetic_identity"
    BUST_OUT = "bust_out"
    FIRST_PARTY_FRAUD = "first_party_fraud"
    IDENTITY_THEFT = "identity_theft"
    APPLICATION_FRAUD = "application_fraud"


@dataclass
class ConsortiumAlert:
    """Fraud alert from industry consortium."""

    alert_id: str
    alert_type: AlertType
    ssn_hash: Optional[str]
    identity_hash: str
    reported_by: str
    reported_date: datetime
    confidence_score: float
    details: dict
    related_identities: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "ConsortiumAlert":
        """Create from dictionary."""
        return cls(
            alert_id=data["alert_id"],
            alert_type=AlertType(data["alert_type"]),
            ssn_hash=data.get("ssn_hash"),
            identity_hash=data["identity_hash"],
            reported_by=data["reported_by"],
            reported_date=datetime.fromisoformat(data["reported_date"]),
            confidence_score=data["confidence_score"],
            details=data.get("details", {}),
            related_identities=data.get("related_identities", []),
        )


class ConsortiumReceiver:
    """Receives and processes fraud alerts from industry consortium."""

    def __init__(
        self,
        provider: str = "early_warning",
        bootstrap_servers: Optional[str] = None,
    ):
        settings = get_settings()
        self.provider = provider
        self.bootstrap_servers = bootstrap_servers or settings.kafka.bootstrap_servers
        self._consumer: Optional[KafkaConsumer] = None
        self._alert_handlers: dict[AlertType, list] = {t: [] for t in AlertType}

    def connect(self) -> None:
        """Connect to consortium feed."""
        topic = f"consortium-{self.provider}-alerts"
        self._consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=f"fraud-detection-{self.provider}",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
        )
        logger.info(f"Connected to consortium feed: {self.provider}")

    def register_handler(self, alert_type: AlertType, handler) -> None:
        """Register handler for specific alert type."""
        self._alert_handlers[alert_type].append(handler)

    def process_alerts(self) -> None:
        """Process incoming consortium alerts."""
        if not self._consumer:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.info("Processing consortium alerts...")
        for message in self._consumer:
            try:
                alert = ConsortiumAlert.from_dict(message.value)
                logger.info(
                    f"Received {alert.alert_type.value} alert: {alert.alert_id}"
                )

                for handler in self._alert_handlers[alert.alert_type]:
                    handler(alert)

            except Exception as e:
                logger.error(f"Error processing alert: {e}", exc_info=True)

    def get_alerts_for_identity(
        self, identity_hash: str, days_back: int = 90
    ) -> list[ConsortiumAlert]:
        """Query historical alerts for an identity."""
        # TODO: Implement historical query against consortium API
        logger.debug(f"Querying alerts for identity {identity_hash[:8]}")
        return []

    def close(self) -> None:
        """Close consumer connection."""
        if self._consumer:
            self._consumer.close()
            logger.info("Consortium receiver closed")
