"""Track velocity of phone number usage across identities."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PhoneVelocity:
    """Phone number velocity metrics."""

    phone_hash: str
    unique_identities_30d: int
    unique_identities_90d: int
    unique_identities_180d: int
    unique_ssns_30d: int
    unique_ssns_90d: int
    unique_ssns_180d: int
    unique_addresses_180d: int
    first_seen: datetime
    last_seen: datetime
    is_high_velocity: bool
    velocity_score: float


class PhoneVelocityTracker:
    """Tracks how many identities use the same phone number."""

    def __init__(self, redis_client=None):
        """
        Initialize velocity tracker.

        Args:
            redis_client: Redis client for velocity storage
        """
        self._redis = redis_client
        self._settings = get_settings()

    def record_phone_use(
        self,
        phone_hash: str,
        identity_hash: str,
        ssn_hash: str,
        address_hash: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record an identity using a phone number.

        Args:
            phone_hash: Hashed phone number
            identity_hash: Hash of the identity
            ssn_hash: Hash of the SSN
            address_hash: Hash of associated address
            timestamp: When the phone was used
        """
        if timestamp is None:
            timestamp = datetime.now()

        # TODO: Implement Redis storage
        logger.debug(f"Recording phone use: {phone_hash[:8]} by {identity_hash[:8]}")

    def get_velocity(self, phone_hash: str) -> PhoneVelocity:
        """
        Get velocity metrics for a phone number.

        Args:
            phone_hash: Hashed phone number

        Returns:
            PhoneVelocity with usage metrics
        """
        now = datetime.now()

        # TODO: Implement actual Redis queries
        velocity = PhoneVelocity(
            phone_hash=phone_hash,
            unique_identities_30d=0,
            unique_identities_90d=0,
            unique_identities_180d=0,
            unique_ssns_30d=0,
            unique_ssns_90d=0,
            unique_ssns_180d=0,
            unique_addresses_180d=0,
            first_seen=now,
            last_seen=now,
            is_high_velocity=False,
            velocity_score=0.0,
        )

        # Calculate if high velocity
        threshold = self._settings.velocity.phone_max_identities_6mo
        velocity.is_high_velocity = velocity.unique_identities_180d > threshold
        velocity.velocity_score = self._calculate_score(velocity)

        return velocity

    def _calculate_score(self, velocity: PhoneVelocity) -> float:
        """Calculate velocity risk score (0-1)."""
        threshold = self._settings.velocity.phone_max_identities_6mo

        if velocity.unique_identities_180d <= 1:
            return 0.0

        # Phone velocity is more concerning than address
        # (less legitimate reason to share phones)
        ratio = velocity.unique_identities_180d / threshold
        if ratio <= 1.0:
            return ratio * 0.4
        else:
            excess = min(ratio - 1.0, 2.0)
            return 0.4 + (excess * 0.3)

    def get_associated_identities(
        self,
        phone_hash: str,
        days_back: int = 180,
    ) -> list[dict]:
        """
        Get identities associated with this phone.

        Returns:
            List of identity info dicts
        """
        # TODO: Implement Redis query
        return []

    def check_phone_ssn_mismatch(
        self,
        phone_hash: str,
        claimed_ssn_hash: str,
    ) -> dict:
        """
        Check if phone is associated with different SSNs.

        Returns dict with:
        - has_mismatch: bool
        - other_ssn_count: int
        - risk_score: float
        """
        # TODO: Implement check
        return {
            "has_mismatch": False,
            "other_ssn_count": 0,
            "risk_score": 0.0,
        }
