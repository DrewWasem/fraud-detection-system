"""Track velocity of phone number usage across identities."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    is_high_velocity: bool
    velocity_score: float


class PhoneVelocityTracker:
    """Tracks how many identities use the same phone number."""

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
        self._prefix = self._settings.redis.phone_prefix

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

        if not self._redis:
            logger.debug(
                f"Recording phone use (no Redis): {phone_hash[:8]} by {identity_hash[:8]}"
            )
            return

        ts = timestamp.timestamp()

        # Keys for this phone
        identities_key = f"{self._prefix}:{phone_hash}:identities"
        ssns_key = f"{self._prefix}:{phone_hash}:ssns"
        addresses_key = f"{self._prefix}:{phone_hash}:addresses"
        metadata_key = f"{self._prefix}:{phone_hash}:meta"

        try:
            pipe = self._redis.pipeline()

            # Add identity to sorted set (score = timestamp)
            pipe.zadd(identities_key, {identity_hash: ts})

            # Add SSN to sorted set
            pipe.zadd(ssns_key, {ssn_hash: ts})

            # Add address if provided
            if address_hash:
                pipe.zadd(addresses_key, {address_hash: ts})

            # Update metadata
            pipe.hsetnx(metadata_key, "first_seen", timestamp.isoformat())
            pipe.hset(metadata_key, "last_seen", timestamp.isoformat())

            # Set TTL on keys
            ttl = self._settings.redis.velocity_ttl
            pipe.expire(identities_key, ttl)
            pipe.expire(ssns_key, ttl)
            pipe.expire(addresses_key, ttl)
            pipe.expire(metadata_key, ttl)

            pipe.execute()

            logger.debug(
                f"Recorded phone use: {phone_hash[:8]} by {identity_hash[:8]}"
            )

        except Exception as e:
            logger.error(f"Error recording phone use: {e}")

    def get_velocity(self, phone_hash: str) -> PhoneVelocity:
        """
        Get velocity metrics for a phone number.

        Args:
            phone_hash: Hashed phone number

        Returns:
            PhoneVelocity with usage metrics
        """
        now = datetime.now()

        if not self._redis:
            return self._empty_velocity(phone_hash, now)

        # Calculate timestamps for windows
        ts_30d = (now - timedelta(days=self.WINDOW_30D)).timestamp()
        ts_90d = (now - timedelta(days=self.WINDOW_90D)).timestamp()
        ts_180d = (now - timedelta(days=self.WINDOW_180D)).timestamp()

        # Keys for this phone
        identities_key = f"{self._prefix}:{phone_hash}:identities"
        ssns_key = f"{self._prefix}:{phone_hash}:ssns"
        addresses_key = f"{self._prefix}:{phone_hash}:addresses"
        metadata_key = f"{self._prefix}:{phone_hash}:meta"

        try:
            # Count unique identities in each window
            unique_30d = self._redis.zcount(identities_key, ts_30d, "+inf")
            unique_90d = self._redis.zcount(identities_key, ts_90d, "+inf")
            unique_180d = self._redis.zcount(identities_key, ts_180d, "+inf")

            # Count unique SSNs in each window
            ssns_30d = self._redis.zcount(ssns_key, ts_30d, "+inf")
            ssns_90d = self._redis.zcount(ssns_key, ts_90d, "+inf")
            ssns_180d = self._redis.zcount(ssns_key, ts_180d, "+inf")

            # Count unique addresses
            addresses_180d = self._redis.zcount(addresses_key, ts_180d, "+inf")

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

            velocity = PhoneVelocity(
                phone_hash=phone_hash,
                unique_identities_30d=unique_30d,
                unique_identities_90d=unique_90d,
                unique_identities_180d=unique_180d,
                unique_ssns_30d=ssns_30d,
                unique_ssns_90d=ssns_90d,
                unique_ssns_180d=ssns_180d,
                unique_addresses_180d=addresses_180d,
                first_seen=first_seen,
                last_seen=last_seen,
                is_high_velocity=False,
                velocity_score=0.0,
            )

            # Calculate if high velocity
            threshold = self._settings.velocity.phone_max_identities_6mo
            velocity.is_high_velocity = velocity.unique_identities_180d > threshold
            velocity.velocity_score = self._calculate_score(velocity)

            return velocity

        except Exception as e:
            logger.error(f"Error getting phone velocity: {e}")
            return self._empty_velocity(phone_hash, now)

    def _calculate_score(self, velocity: PhoneVelocity) -> float:
        """Calculate velocity risk score (0-1)."""
        threshold = self._settings.velocity.phone_max_identities_6mo

        if velocity.unique_identities_180d <= 1:
            return 0.0

        # Phone velocity is more concerning than address
        # (less legitimate reason to share phones)
        ratio = velocity.unique_identities_180d / threshold
        if ratio <= 1.0:
            base_score = ratio * 0.4
        else:
            excess = min(ratio - 1.0, 2.5)
            base_score = 0.4 + (excess * 0.24)

        # Boost for multiple SSNs (highly suspicious)
        if velocity.unique_ssns_180d > 1:
            ssn_boost = min(0.25, (velocity.unique_ssns_180d - 1) * 0.08)
            base_score += ssn_boost

        # Boost for multiple addresses using same phone
        if velocity.unique_addresses_180d > 2:
            addr_boost = min(0.1, (velocity.unique_addresses_180d - 2) * 0.03)
            base_score += addr_boost

        # Boost for recent velocity
        if velocity.unique_identities_180d > 0:
            recency_ratio = velocity.unique_identities_30d / velocity.unique_identities_180d
            if recency_ratio > 0.5:
                base_score *= 1.2

        return min(1.0, base_score)

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
        if not self._redis:
            return []

        min_ts = (datetime.now() - timedelta(days=days_back)).timestamp()
        identities_key = f"{self._prefix}:{phone_hash}:identities"

        try:
            # Get identities with their timestamps
            results = self._redis.zrangebyscore(
                identities_key, min_ts, "+inf", withscores=True
            )

            identities = []
            for identity, ts in results:
                identity_str = identity.decode() if isinstance(identity, bytes) else identity
                identities.append({
                    "identity_hash": identity_str,
                    "timestamp": datetime.fromtimestamp(ts).isoformat(),
                })

            return identities

        except Exception as e:
            logger.error(f"Error getting associated identities: {e}")
            return []

    def get_associated_ssns(
        self,
        phone_hash: str,
        days_back: int = 180,
    ) -> list[str]:
        """
        Get SSN hashes associated with this phone.

        Returns:
            List of SSN hashes
        """
        if not self._redis:
            return []

        min_ts = (datetime.now() - timedelta(days=days_back)).timestamp()
        ssns_key = f"{self._prefix}:{phone_hash}:ssns"

        try:
            ssns = self._redis.zrangebyscore(ssns_key, min_ts, "+inf")
            return [s.decode() if isinstance(s, bytes) else s for s in ssns]
        except Exception as e:
            logger.error(f"Error getting associated SSNs: {e}")
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
        if not self._redis:
            return {
                "has_mismatch": False,
                "other_ssn_count": 0,
                "risk_score": 0.0,
            }

        try:
            ssns = self.get_associated_ssns(phone_hash)

            # Filter out the claimed SSN
            other_ssns = [s for s in ssns if s != claimed_ssn_hash]
            other_count = len(other_ssns)

            has_mismatch = other_count > 0

            # Calculate risk score
            if not has_mismatch:
                risk_score = 0.0
            elif other_count == 1:
                risk_score = 0.5
            elif other_count == 2:
                risk_score = 0.7
            else:
                risk_score = min(1.0, 0.7 + (other_count - 2) * 0.1)

            return {
                "has_mismatch": has_mismatch,
                "other_ssn_count": other_count,
                "risk_score": risk_score,
            }

        except Exception as e:
            logger.error(f"Error checking phone-SSN mismatch: {e}")
            return {
                "has_mismatch": False,
                "other_ssn_count": 0,
                "risk_score": 0.0,
            }

    def _empty_velocity(
        self, phone_hash: str, now: datetime
    ) -> PhoneVelocity:
        """Return empty velocity metrics."""
        return PhoneVelocity(
            phone_hash=phone_hash,
            unique_identities_30d=0,
            unique_identities_90d=0,
            unique_identities_180d=0,
            unique_ssns_30d=0,
            unique_ssns_90d=0,
            unique_ssns_180d=0,
            unique_addresses_180d=0,
            first_seen=None,
            last_seen=None,
            is_high_velocity=False,
            velocity_score=0.0,
        )
