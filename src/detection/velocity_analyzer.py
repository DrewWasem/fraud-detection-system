"""PII velocity analysis for fraud detection."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class VelocityAnalysis:
    """Combined velocity analysis result."""

    identity_id: str
    address_velocity: float
    phone_velocity: float
    email_velocity: float
    device_velocity: float
    overall_velocity_score: float
    anomalies: list[str]
    risk_level: str


class VelocityAnalyzer:
    """Analyzes velocity of PII element usage."""

    def __init__(self, redis_client=None):
        """
        Initialize analyzer.

        Args:
            redis_client: Redis client for velocity data
        """
        self._redis = redis_client
        self._settings = get_settings()

    def analyze(
        self,
        identity_id: str,
        ssn_hash: str,
        address_hash: str,
        phone_hash: str,
        email_hash: str,
        device_fingerprint: Optional[str] = None,
    ) -> VelocityAnalysis:
        """
        Analyze velocity for all identity elements.

        Args:
            identity_id: Identity being analyzed
            ssn_hash: Hashed SSN
            address_hash: Normalized address hash
            phone_hash: Hashed phone
            email_hash: Email address
            device_fingerprint: Optional device fingerprint

        Returns:
            VelocityAnalysis with findings
        """
        # Get velocity for each element
        address_velocity = self._get_address_velocity(address_hash)
        phone_velocity = self._get_phone_velocity(phone_hash)
        email_velocity = self._get_email_velocity(email_hash)
        device_velocity = (
            self._get_device_velocity(device_fingerprint)
            if device_fingerprint
            else 0.0
        )

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            address_velocity, phone_velocity, email_velocity, device_velocity
        )

        # Identify anomalies
        anomalies = self._identify_anomalies(
            address_velocity, phone_velocity, email_velocity, device_velocity
        )

        # Determine risk level
        risk_level = self._determine_risk_level(overall_score, anomalies)

        return VelocityAnalysis(
            identity_id=identity_id,
            address_velocity=address_velocity,
            phone_velocity=phone_velocity,
            email_velocity=email_velocity,
            device_velocity=device_velocity,
            overall_velocity_score=overall_score,
            anomalies=anomalies,
            risk_level=risk_level,
        )

    def _get_address_velocity(self, address_hash: str) -> float:
        """Get velocity score for address."""
        # TODO: Implement actual Redis lookup
        # For now, return placeholder
        return 0.0

    def _get_phone_velocity(self, phone_hash: str) -> float:
        """Get velocity score for phone."""
        # TODO: Implement actual Redis lookup
        return 0.0

    def _get_email_velocity(self, email_hash: str) -> float:
        """Get velocity score for email."""
        # TODO: Implement actual Redis lookup
        return 0.0

    def _get_device_velocity(self, device_fingerprint: str) -> float:
        """Get velocity score for device."""
        # TODO: Implement actual Redis lookup
        return 0.0

    def _calculate_overall_score(
        self,
        address: float,
        phone: float,
        email: float,
        device: float,
    ) -> float:
        """Calculate weighted overall velocity score."""
        # Weights for different elements
        weights = {
            "address": 0.25,
            "phone": 0.35,  # Phone sharing is more suspicious
            "email": 0.20,
            "device": 0.20,
        }

        total = (
            address * weights["address"]
            + phone * weights["phone"]
            + email * weights["email"]
            + device * weights["device"]
        )

        return min(1.0, total)

    def _identify_anomalies(
        self,
        address: float,
        phone: float,
        email: float,
        device: float,
    ) -> list[str]:
        """Identify velocity anomalies."""
        anomalies = []

        thresholds = self._settings.velocity

        if address > 0.5:
            anomalies.append(f"HIGH_ADDRESS_VELOCITY")

        if phone > 0.5:
            anomalies.append(f"HIGH_PHONE_VELOCITY")

        if email > 0.5:
            anomalies.append(f"HIGH_EMAIL_VELOCITY")

        if device > 0.5:
            anomalies.append(f"SHARED_DEVICE")

        # Check for unusual combinations
        if address > 0.3 and phone > 0.3:
            anomalies.append("ADDRESS_PHONE_CORRELATION")

        return anomalies

    def _determine_risk_level(
        self, overall_score: float, anomalies: list[str]
    ) -> str:
        """Determine risk level from velocity analysis."""
        if overall_score >= 0.8 or len(anomalies) >= 4:
            return "critical"
        elif overall_score >= 0.6 or len(anomalies) >= 3:
            return "high"
        elif overall_score >= 0.4 or len(anomalies) >= 2:
            return "medium"
        elif overall_score >= 0.2 or len(anomalies) >= 1:
            return "low"
        else:
            return "minimal"

    def record_element_use(
        self,
        element_type: str,
        element_hash: str,
        identity_hash: str,
        ssn_hash: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record use of a PII element by an identity.

        Args:
            element_type: Type of element (address, phone, email, device)
            element_hash: Hash of the element
            identity_hash: Hash of the identity
            ssn_hash: Hash of the SSN
            timestamp: When the element was used
        """
        if timestamp is None:
            timestamp = datetime.now()

        # TODO: Implement Redis storage
        # ZADD element:{type}:{hash}:identities {timestamp} {identity_hash}
        # ZADD element:{type}:{hash}:ssns {timestamp} {ssn_hash}
        logger.debug(
            f"Recording {element_type} use: {element_hash[:8]} by {identity_hash[:8]}"
        )

    def get_element_history(
        self,
        element_type: str,
        element_hash: str,
        days_back: int = 180,
    ) -> dict:
        """
        Get usage history for an element.

        Returns:
            dict with identities, ssns, first_seen, last_seen
        """
        # TODO: Implement actual lookup
        return {
            "identities": [],
            "ssns": [],
            "first_seen": None,
            "last_seen": None,
        }
