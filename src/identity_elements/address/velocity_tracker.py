"""Track velocity of address usage across identities."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AddressVelocity:
    """Address velocity metrics."""

    address_hash: str
    unique_identities_30d: int
    unique_identities_90d: int
    unique_identities_180d: int
    unique_ssns_30d: int
    unique_ssns_90d: int
    unique_ssns_180d: int
    first_seen: datetime
    last_seen: datetime
    is_high_velocity: bool
    velocity_score: float


class AddressVelocityTracker:
    """Tracks how many identities use the same address over time."""

    def __init__(self, redis_client=None):
        """
        Initialize velocity tracker.

        Args:
            redis_client: Redis client for velocity storage
        """
        self._redis = redis_client
        self._settings = get_settings()

    def record_address_use(
        self,
        address_hash: str,
        identity_hash: str,
        ssn_hash: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record an identity using an address.

        Args:
            address_hash: Normalized address hash
            identity_hash: Hash of the identity using the address
            ssn_hash: Hash of the SSN
            timestamp: When the address was used
        """
        if timestamp is None:
            timestamp = datetime.now()

        # TODO: Implement Redis sorted set storage
        # ZADD address:{hash}:identities {timestamp} {identity_hash}
        # ZADD address:{hash}:ssns {timestamp} {ssn_hash}
        logger.debug(
            f"Recording address use: {address_hash[:8]} by {identity_hash[:8]}"
        )

    def get_velocity(self, address_hash: str) -> AddressVelocity:
        """
        Get velocity metrics for an address.

        Args:
            address_hash: Normalized address hash

        Returns:
            AddressVelocity with usage metrics
        """
        now = datetime.now()

        # TODO: Implement actual Redis queries
        # For now, return placeholder
        velocity = AddressVelocity(
            address_hash=address_hash,
            unique_identities_30d=0,
            unique_identities_90d=0,
            unique_identities_180d=0,
            unique_ssns_30d=0,
            unique_ssns_90d=0,
            unique_ssns_180d=0,
            first_seen=now,
            last_seen=now,
            is_high_velocity=False,
            velocity_score=0.0,
        )

        # Calculate if high velocity
        threshold = self._settings.velocity.address_max_identities_6mo
        velocity.is_high_velocity = velocity.unique_identities_180d > threshold
        velocity.velocity_score = self._calculate_score(velocity)

        return velocity

    def _calculate_score(self, velocity: AddressVelocity) -> float:
        """Calculate velocity risk score (0-1)."""
        threshold = self._settings.velocity.address_max_identities_6mo

        if velocity.unique_identities_180d <= 1:
            return 0.0

        # Score increases as we exceed threshold
        ratio = velocity.unique_identities_180d / threshold
        if ratio <= 1.0:
            return ratio * 0.3  # Below threshold, low score
        else:
            # Above threshold, higher score
            excess = min(ratio - 1.0, 2.0)  # Cap at 3x threshold
            return 0.3 + (excess * 0.35)

    def get_shared_identities(
        self,
        address_hash: str,
        days_back: int = 180,
    ) -> list[str]:
        """
        Get list of identity hashes that have used this address.

        Args:
            address_hash: Normalized address hash
            days_back: How far back to look

        Returns:
            List of identity hashes
        """
        # TODO: Implement Redis query
        return []

    def get_address_cluster(
        self,
        address_hash: str,
        min_shared_identities: int = 2,
    ) -> dict:
        """
        Get cluster of addresses linked by shared identities.

        Returns addresses that share identities with the given address.
        """
        # TODO: Implement graph traversal
        return {
            "center_address": address_hash,
            "linked_addresses": [],
            "shared_identities": [],
        }
