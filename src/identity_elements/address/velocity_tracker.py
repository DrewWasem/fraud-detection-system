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
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    is_high_velocity: bool
    velocity_score: float


class AddressVelocityTracker:
    """Tracks how many identities use the same address over time."""

    # Time windows in days
    WINDOW_30D = 30
    WINDOW_90D = 90
    WINDOW_180D = 180

    def __init__(self, redis_client=None):
        """
        Initialize velocity tracker.

        Args:
            redis_client: Redis client for velocity storage
        """
        self._redis = redis_client
        self._settings = get_settings()
        self._prefix = self._settings.redis.address_prefix

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

        if not self._redis:
            logger.debug(
                f"Recording address use (no Redis): {address_hash[:8]} by {identity_hash[:8]}"
            )
            return

        ts = timestamp.timestamp()

        # Keys for this address
        identities_key = f"{self._prefix}:{address_hash}:identities"
        ssns_key = f"{self._prefix}:{address_hash}:ssns"
        metadata_key = f"{self._prefix}:{address_hash}:meta"

        try:
            pipe = self._redis.pipeline()

            # Add identity to sorted set (score = timestamp)
            pipe.zadd(identities_key, {identity_hash: ts})

            # Add SSN to sorted set
            pipe.zadd(ssns_key, {ssn_hash: ts})

            # Update metadata
            pipe.hsetnx(metadata_key, "first_seen", timestamp.isoformat())
            pipe.hset(metadata_key, "last_seen", timestamp.isoformat())

            # Set TTL on keys
            ttl = self._settings.redis.velocity_ttl
            pipe.expire(identities_key, ttl)
            pipe.expire(ssns_key, ttl)
            pipe.expire(metadata_key, ttl)

            pipe.execute()

            logger.debug(
                f"Recorded address use: {address_hash[:8]} by {identity_hash[:8]}"
            )

        except Exception as e:
            logger.error(f"Error recording address use: {e}")

    def get_velocity(self, address_hash: str) -> AddressVelocity:
        """
        Get velocity metrics for an address.

        Args:
            address_hash: Normalized address hash

        Returns:
            AddressVelocity with usage metrics
        """
        now = datetime.now()

        if not self._redis:
            return self._empty_velocity(address_hash, now)

        # Calculate timestamps for windows
        ts_30d = (now - timedelta(days=self.WINDOW_30D)).timestamp()
        ts_90d = (now - timedelta(days=self.WINDOW_90D)).timestamp()
        ts_180d = (now - timedelta(days=self.WINDOW_180D)).timestamp()

        # Keys for this address
        identities_key = f"{self._prefix}:{address_hash}:identities"
        ssns_key = f"{self._prefix}:{address_hash}:ssns"
        metadata_key = f"{self._prefix}:{address_hash}:meta"

        try:
            # Count unique identities in each window
            unique_30d = self._redis.zcount(identities_key, ts_30d, "+inf")
            unique_90d = self._redis.zcount(identities_key, ts_90d, "+inf")
            unique_180d = self._redis.zcount(identities_key, ts_180d, "+inf")

            # Count unique SSNs in each window
            ssns_30d = self._redis.zcount(ssns_key, ts_30d, "+inf")
            ssns_90d = self._redis.zcount(ssns_key, ts_90d, "+inf")
            ssns_180d = self._redis.zcount(ssns_key, ts_180d, "+inf")

            # Get metadata
            metadata = self._redis.hgetall(metadata_key)
            first_seen = None
            last_seen = None
            if metadata:
                if b"first_seen" in metadata:
                    first_seen = datetime.fromisoformat(
                        metadata[b"first_seen"].decode()
                    )
                elif "first_seen" in metadata:
                    first_seen = datetime.fromisoformat(metadata["first_seen"])
                if b"last_seen" in metadata:
                    last_seen = datetime.fromisoformat(
                        metadata[b"last_seen"].decode()
                    )
                elif "last_seen" in metadata:
                    last_seen = datetime.fromisoformat(metadata["last_seen"])

            velocity = AddressVelocity(
                address_hash=address_hash,
                unique_identities_30d=unique_30d,
                unique_identities_90d=unique_90d,
                unique_identities_180d=unique_180d,
                unique_ssns_30d=ssns_30d,
                unique_ssns_90d=ssns_90d,
                unique_ssns_180d=ssns_180d,
                first_seen=first_seen,
                last_seen=last_seen,
                is_high_velocity=False,
                velocity_score=0.0,
            )

            # Calculate if high velocity
            threshold = self._settings.velocity.address_max_identities_6mo
            velocity.is_high_velocity = velocity.unique_identities_180d > threshold
            velocity.velocity_score = self._calculate_score(velocity)

            return velocity

        except Exception as e:
            logger.error(f"Error getting address velocity: {e}")
            return self._empty_velocity(address_hash, now)

    def _calculate_score(self, velocity: AddressVelocity) -> float:
        """Calculate velocity risk score (0-1)."""
        threshold = self._settings.velocity.address_max_identities_6mo

        if velocity.unique_identities_180d <= 1:
            return 0.0

        # Score increases as we exceed threshold
        ratio = velocity.unique_identities_180d / threshold
        if ratio <= 1.0:
            base_score = ratio * 0.3  # Below threshold, low score
        else:
            # Above threshold, higher score
            excess = min(ratio - 1.0, 3.0)
            base_score = 0.3 + (excess * 0.233)

        # Boost for multiple SSNs
        if velocity.unique_ssns_180d > 1:
            ssn_boost = min(0.2, (velocity.unique_ssns_180d - 1) * 0.05)
            base_score += ssn_boost

        # Boost for recent velocity
        if velocity.unique_identities_180d > 0:
            recency_ratio = velocity.unique_identities_30d / velocity.unique_identities_180d
            if recency_ratio > 0.5:
                base_score *= 1.2

        return min(1.0, base_score)

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
        if not self._redis:
            return []

        min_ts = (datetime.now() - timedelta(days=days_back)).timestamp()
        identities_key = f"{self._prefix}:{address_hash}:identities"

        try:
            identities = self._redis.zrangebyscore(identities_key, min_ts, "+inf")
            return [
                i.decode() if isinstance(i, bytes) else i for i in identities
            ]
        except Exception as e:
            logger.error(f"Error getting shared identities: {e}")
            return []

    def get_shared_ssns(
        self,
        address_hash: str,
        days_back: int = 180,
    ) -> list[str]:
        """
        Get list of SSN hashes that have used this address.

        Args:
            address_hash: Normalized address hash
            days_back: How far back to look

        Returns:
            List of SSN hashes
        """
        if not self._redis:
            return []

        min_ts = (datetime.now() - timedelta(days=days_back)).timestamp()
        ssns_key = f"{self._prefix}:{address_hash}:ssns"

        try:
            ssns = self._redis.zrangebyscore(ssns_key, min_ts, "+inf")
            return [s.decode() if isinstance(s, bytes) else s for s in ssns]
        except Exception as e:
            logger.error(f"Error getting shared SSNs: {e}")
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
        if not self._redis:
            return {
                "center_address": address_hash,
                "linked_addresses": [],
                "shared_identities": [],
            }

        try:
            # Get identities using this address
            identities = self.get_shared_identities(address_hash)

            if len(identities) < min_shared_identities:
                return {
                    "center_address": address_hash,
                    "linked_addresses": [],
                    "shared_identities": identities,
                }

            # Find other addresses used by these identities
            # This would require reverse lookup - for now return basic info
            return {
                "center_address": address_hash,
                "linked_addresses": [],
                "shared_identities": identities,
            }

        except Exception as e:
            logger.error(f"Error getting address cluster: {e}")
            return {
                "center_address": address_hash,
                "linked_addresses": [],
                "shared_identities": [],
            }

    def _empty_velocity(
        self, address_hash: str, now: datetime
    ) -> AddressVelocity:
        """Return empty velocity metrics."""
        return AddressVelocity(
            address_hash=address_hash,
            unique_identities_30d=0,
            unique_identities_90d=0,
            unique_identities_180d=0,
            unique_ssns_30d=0,
            unique_ssns_90d=0,
            unique_ssns_180d=0,
            first_seen=None,
            last_seen=None,
            is_high_velocity=False,
            velocity_score=0.0,
        )
