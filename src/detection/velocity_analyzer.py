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


@dataclass
class ElementVelocity:
    """Velocity metrics for a single element."""

    element_hash: str
    element_type: str
    unique_identities_30d: int
    unique_identities_90d: int
    unique_identities_180d: int
    unique_ssns_30d: int
    unique_ssns_90d: int
    unique_ssns_180d: int
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    velocity_score: float


class VelocityAnalyzer:
    """Analyzes velocity of PII element usage."""

    # Time windows in days
    WINDOW_30D = 30
    WINDOW_90D = 90
    WINDOW_180D = 180

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

    def _get_element_velocity(
        self, element_type: str, element_hash: str
    ) -> ElementVelocity:
        """Get velocity metrics for any element type."""
        if not self._redis:
            return self._empty_element_velocity(element_hash, element_type)

        prefix = self._get_prefix(element_type)
        now = datetime.now()

        # Calculate timestamps for windows
        ts_30d = (now - timedelta(days=self.WINDOW_30D)).timestamp()
        ts_90d = (now - timedelta(days=self.WINDOW_90D)).timestamp()
        ts_180d = (now - timedelta(days=self.WINDOW_180D)).timestamp()

        # Keys for this element
        identities_key = f"{prefix}:{element_hash}:identities"
        ssns_key = f"{prefix}:{element_hash}:ssns"
        metadata_key = f"{prefix}:{element_hash}:meta"

        try:
            # Count unique identities in each window using ZCOUNT
            unique_30d = self._redis.zcount(identities_key, ts_30d, "+inf")
            unique_90d = self._redis.zcount(identities_key, ts_90d, "+inf")
            unique_180d = self._redis.zcount(identities_key, ts_180d, "+inf")

            # Count unique SSNs in each window
            ssns_30d = self._redis.zcount(ssns_key, ts_30d, "+inf")
            ssns_90d = self._redis.zcount(ssns_key, ts_90d, "+inf")
            ssns_180d = self._redis.zcount(ssns_key, ts_180d, "+inf")

            # Get first_seen and last_seen from metadata
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

            velocity = ElementVelocity(
                element_hash=element_hash,
                element_type=element_type,
                unique_identities_30d=unique_30d,
                unique_identities_90d=unique_90d,
                unique_identities_180d=unique_180d,
                unique_ssns_30d=ssns_30d,
                unique_ssns_90d=ssns_90d,
                unique_ssns_180d=ssns_180d,
                first_seen=first_seen,
                last_seen=last_seen,
                velocity_score=0.0,
            )

            # Calculate velocity score
            velocity.velocity_score = self._calculate_element_score(
                element_type, velocity
            )
            return velocity

        except Exception as e:
            logger.error(f"Error getting velocity for {element_type}: {e}")
            return self._empty_element_velocity(element_hash, element_type)

    def _get_prefix(self, element_type: str) -> str:
        """Get Redis key prefix for element type."""
        prefixes = {
            "address": self._settings.redis.address_prefix,
            "phone": self._settings.redis.phone_prefix,
            "email": self._settings.redis.email_prefix,
            "device": self._settings.redis.device_prefix,
        }
        return prefixes.get(element_type, f"velocity:{element_type}")

    def _get_address_velocity(self, address_hash: str) -> float:
        """Get velocity score for address."""
        velocity = self._get_element_velocity("address", address_hash)
        return velocity.velocity_score

    def _get_phone_velocity(self, phone_hash: str) -> float:
        """Get velocity score for phone."""
        velocity = self._get_element_velocity("phone", phone_hash)
        return velocity.velocity_score

    def _get_email_velocity(self, email_hash: str) -> float:
        """Get velocity score for email."""
        velocity = self._get_element_velocity("email", email_hash)
        return velocity.velocity_score

    def _get_device_velocity(self, device_fingerprint: str) -> float:
        """Get velocity score for device."""
        velocity = self._get_element_velocity("device", device_fingerprint)
        return velocity.velocity_score

    def _calculate_element_score(
        self, element_type: str, velocity: ElementVelocity
    ) -> float:
        """Calculate velocity risk score for an element (0-1)."""
        # Get threshold based on element type
        thresholds = {
            "address": self._settings.velocity.address_max_identities_6mo,
            "phone": self._settings.velocity.phone_max_identities_6mo,
            "email": self._settings.velocity.email_max_identities_6mo,
            "device": 3,  # Devices shouldn't be shared much
        }
        threshold = thresholds.get(element_type, 5)

        if velocity.unique_identities_180d <= 1:
            return 0.0

        # Base score from identity count vs threshold
        ratio = velocity.unique_identities_180d / threshold
        if ratio <= 1.0:
            base_score = ratio * 0.3
        else:
            # Above threshold, escalate quickly
            excess = min(ratio - 1.0, 3.0)
            base_score = 0.3 + (excess * 0.233)  # Max of 1.0 at 4x threshold

        # Boost score if multiple SSNs use this element
        if velocity.unique_ssns_180d > 1:
            ssn_boost = min(0.2, (velocity.unique_ssns_180d - 1) * 0.05)
            base_score += ssn_boost

        # Boost for rapid recent velocity (30d vs 180d)
        if velocity.unique_identities_180d > 0:
            recency_ratio = velocity.unique_identities_30d / velocity.unique_identities_180d
            if recency_ratio > 0.5:  # More than half in last 30 days
                base_score *= 1.2

        return min(1.0, base_score)

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

        if address > 0.5:
            anomalies.append("HIGH_ADDRESS_VELOCITY")

        if phone > 0.5:
            anomalies.append("HIGH_PHONE_VELOCITY")

        if email > 0.5:
            anomalies.append("HIGH_EMAIL_VELOCITY")

        if device > 0.5:
            anomalies.append("SHARED_DEVICE")

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

        if not self._redis:
            logger.debug(
                f"Recording {element_type} use (no Redis): "
                f"{element_hash[:8]} by {identity_hash[:8]}"
            )
            return

        prefix = self._get_prefix(element_type)
        ts = timestamp.timestamp()

        # Keys for this element
        identities_key = f"{prefix}:{element_hash}:identities"
        ssns_key = f"{prefix}:{element_hash}:ssns"
        metadata_key = f"{prefix}:{element_hash}:meta"

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
                f"Recorded {element_type} use: {element_hash[:8]} by {identity_hash[:8]}"
            )

        except Exception as e:
            logger.error(f"Error recording {element_type} use: {e}")

    def record_identity_elements(
        self,
        identity_hash: str,
        ssn_hash: str,
        address_hash: str,
        phone_hash: str,
        email_hash: str,
        device_fingerprint: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record all PII elements for an identity at once.

        Args:
            identity_hash: Hash of the identity
            ssn_hash: Hash of the SSN
            address_hash: Normalized address hash
            phone_hash: Hashed phone
            email_hash: Hashed email
            device_fingerprint: Optional device fingerprint
            timestamp: When the elements were used
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.record_element_use("address", address_hash, identity_hash, ssn_hash, timestamp)
        self.record_element_use("phone", phone_hash, identity_hash, ssn_hash, timestamp)
        self.record_element_use("email", email_hash, identity_hash, ssn_hash, timestamp)

        if device_fingerprint:
            self.record_element_use(
                "device", device_fingerprint, identity_hash, ssn_hash, timestamp
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
        if not self._redis:
            return {
                "identities": [],
                "ssns": [],
                "first_seen": None,
                "last_seen": None,
            }

        prefix = self._get_prefix(element_type)
        min_ts = (datetime.now() - timedelta(days=days_back)).timestamp()

        identities_key = f"{prefix}:{element_hash}:identities"
        ssns_key = f"{prefix}:{element_hash}:ssns"
        metadata_key = f"{prefix}:{element_hash}:meta"

        try:
            # Get all identities in window
            identities = self._redis.zrangebyscore(
                identities_key, min_ts, "+inf"
            )

            # Get all SSNs in window
            ssns = self._redis.zrangebyscore(ssns_key, min_ts, "+inf")

            # Get metadata
            metadata = self._redis.hgetall(metadata_key)
            first_seen = None
            last_seen = None
            if metadata:
                if b"first_seen" in metadata:
                    first_seen = metadata[b"first_seen"].decode()
                elif "first_seen" in metadata:
                    first_seen = metadata["first_seen"]
                if b"last_seen" in metadata:
                    last_seen = metadata[b"last_seen"].decode()
                elif "last_seen" in metadata:
                    last_seen = metadata["last_seen"]

            # Decode bytes if needed
            identities = [
                i.decode() if isinstance(i, bytes) else i for i in identities
            ]
            ssns = [s.decode() if isinstance(s, bytes) else s for s in ssns]

            return {
                "identities": identities,
                "ssns": ssns,
                "first_seen": first_seen,
                "last_seen": last_seen,
            }

        except Exception as e:
            logger.error(f"Error getting history for {element_type}: {e}")
            return {
                "identities": [],
                "ssns": [],
                "first_seen": None,
                "last_seen": None,
            }

    def cleanup_old_data(self, element_type: str, days: int = 180) -> int:
        """
        Remove velocity data older than specified days.

        Returns:
            Number of entries removed
        """
        if not self._redis:
            return 0

        prefix = self._get_prefix(element_type)
        max_ts = (datetime.now() - timedelta(days=days)).timestamp()
        removed = 0

        try:
            # Find all keys matching the pattern
            pattern = f"{prefix}:*:identities"
            cursor = 0

            while True:
                cursor, keys = self._redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    # Remove entries older than max_ts
                    count = self._redis.zremrangebyscore(key, "-inf", max_ts)
                    removed += count

                    # Also clean corresponding SSN key
                    ssn_key = key.replace(b":identities", b":ssns")
                    self._redis.zremrangebyscore(ssn_key, "-inf", max_ts)

                if cursor == 0:
                    break

            return removed

        except Exception as e:
            logger.error(f"Error cleaning up {element_type} data: {e}")
            return removed

    def _empty_element_velocity(
        self, element_hash: str, element_type: str
    ) -> ElementVelocity:
        """Return empty velocity for when Redis is unavailable."""
        return ElementVelocity(
            element_hash=element_hash,
            element_type=element_type,
            unique_identities_30d=0,
            unique_identities_90d=0,
            unique_identities_180d=0,
            unique_ssns_30d=0,
            unique_ssns_90d=0,
            unique_ssns_180d=0,
            first_seen=None,
            last_seen=None,
            velocity_score=0.0,
        )
