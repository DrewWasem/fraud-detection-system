"""Credit application ingestion from Kafka."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from kafka import KafkaConsumer

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CreditApplication:
    """Represents a credit application."""

    application_id: str
    ssn_hash: str
    ssn_last4: str
    ssn_first5: str
    dob: datetime
    first_name: str
    last_name: str
    address_street: str
    address_city: str
    address_state: str
    address_zip: str
    phone: str
    email: str
    application_date: datetime
    application_type: str
    requested_amount: Optional[float] = None
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "CreditApplication":
        """Create from dictionary."""
        return cls(
            application_id=data["application_id"],
            ssn_hash=data["ssn_hash"],
            ssn_last4=data["ssn_last4"],
            ssn_first5=data["ssn_first5"],
            dob=datetime.fromisoformat(data["dob"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            address_street=data["address"]["street"],
            address_city=data["address"]["city"],
            address_state=data["address"]["state"],
            address_zip=data["address"]["zip"],
            phone=data["phone"],
            email=data["email"],
            application_date=datetime.fromisoformat(data["application_date"]),
            application_type=data.get("application_type", "credit_card"),
            requested_amount=data.get("requested_amount"),
            device_fingerprint=data.get("device_fingerprint"),
            ip_address=data.get("ip_address"),
        )


class ApplicationConsumer:
    """Consumes credit applications from Kafka for fraud scoring."""

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: Optional[str] = None,
        group_id: str = "fraud-detection",
    ):
        settings = get_settings()
        self.bootstrap_servers = bootstrap_servers or settings.kafka.bootstrap_servers
        self.topic = topic or settings.kafka.applications_topic
        self.group_id = group_id
        self._consumer: Optional[KafkaConsumer] = None
        self._handlers: list[Callable[[CreditApplication], None]] = []

    def connect(self) -> None:
        """Connect to Kafka."""
        self._consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        logger.info(f"Connected to Kafka topic: {self.topic}")

    def register_handler(
        self, handler: Callable[[CreditApplication], None]
    ) -> None:
        """Register a handler for incoming applications."""
        self._handlers.append(handler)

    def process_messages(self) -> None:
        """Process incoming messages."""
        if not self._consumer:
            raise RuntimeError("Consumer not connected. Call connect() first.")

        logger.info("Starting message processing...")
        for message in self._consumer:
            try:
                application = CreditApplication.from_dict(message.value)
                logger.debug(f"Processing application: {application.application_id}")

                for handler in self._handlers:
                    handler(application)

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

    def close(self) -> None:
        """Close the consumer connection."""
        if self._consumer:
            self._consumer.close()
            logger.info("Consumer connection closed")


def main():
    """Run the application consumer."""
    logging.basicConfig(level=logging.INFO)

    consumer = ApplicationConsumer()
    consumer.connect()

    # Register scoring handler
    def score_application(app: CreditApplication):
        logger.info(f"Scoring application {app.application_id}")
        # TODO: Integrate with synthetic scorer

    consumer.register_handler(score_application)
    consumer.process_messages()


if __name__ == "__main__":
    main()
