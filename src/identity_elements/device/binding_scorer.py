"""Device-identity binding strength scoring."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class BindingStrength:
    """Device-identity binding assessment."""

    identity_hash: str
    device_fingerprint: str
    binding_score: float  # 0-1, higher = stronger binding
    days_associated: int
    interaction_count: int
    is_primary_device: bool
    other_device_count: int
    consistency_score: float


@dataclass
class DeviceHistory:
    """History of devices used by an identity."""

    identity_hash: str
    devices: list[str]
    primary_device: Optional[str]
    device_change_frequency: float  # Changes per month
    has_suspicious_pattern: bool


class DeviceBindingScorer:
    """Scores the strength of device-identity binding."""

    # Redis key prefixes
    KEY_PREFIX = "binding"
    TTL_DAYS = 180

    def __init__(self, redis_client=None):
        """
        Initialize binding scorer.

        Args:
            redis_client: Redis for binding data storage
        """
        self._redis = redis_client

    def record_interaction(
        self,
        identity_hash: str,
        device_fingerprint: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record an identity-device interaction.

        Args:
            identity_hash: Hash of the identity
            device_fingerprint: Device fingerprint ID
            timestamp: When the interaction occurred
        """
        if timestamp is None:
            timestamp = datetime.now()

        logger.debug(
            f"Recording interaction: {identity_hash[:8]} on {device_fingerprint[:8]}"
        )

        if not self._redis:
            return

        try:
            # Store device for identity with interaction count as score
            identity_devices_key = f"{self.KEY_PREFIX}:identity:{identity_hash}:devices"
            self._redis.zincrby(identity_devices_key, 1, device_fingerprint)
            self._redis.expire(identity_devices_key, self.TTL_DAYS * 24 * 60 * 60)

            # Store identity for device with interaction count as score
            device_identities_key = f"{self.KEY_PREFIX}:device:{device_fingerprint}:identities"
            self._redis.zincrby(device_identities_key, 1, identity_hash)
            self._redis.expire(device_identities_key, self.TTL_DAYS * 24 * 60 * 60)

            # Record interaction timestamp
            interactions_key = f"{self.KEY_PREFIX}:{identity_hash}:{device_fingerprint}:times"
            self._redis.zadd(interactions_key, {timestamp.isoformat(): timestamp.timestamp()})
            self._redis.expire(interactions_key, self.TTL_DAYS * 24 * 60 * 60)

            # Update first/last seen
            meta_key = f"{self.KEY_PREFIX}:{identity_hash}:{device_fingerprint}:meta"
            meta = self._redis.hgetall(meta_key)
            if not meta:
                self._redis.hset(meta_key, mapping={
                    'first_seen': timestamp.isoformat(),
                    'last_seen': timestamp.isoformat(),
                })
            else:
                self._redis.hset(meta_key, 'last_seen', timestamp.isoformat())
            self._redis.expire(meta_key, self.TTL_DAYS * 24 * 60 * 60)

        except Exception as e:
            logger.warning(f"Failed to record interaction: {e}")

    def get_binding_strength(
        self,
        identity_hash: str,
        device_fingerprint: str,
    ) -> BindingStrength:
        """
        Calculate binding strength between identity and device.

        Args:
            identity_hash: Hash of the identity
            device_fingerprint: Device fingerprint ID

        Returns:
            BindingStrength assessment
        """
        if not self._redis:
            return BindingStrength(
                identity_hash=identity_hash,
                device_fingerprint=device_fingerprint,
                binding_score=0.0,
                days_associated=0,
                interaction_count=0,
                is_primary_device=False,
                other_device_count=0,
                consistency_score=0.0,
            )

        try:
            # Get interaction count for this device
            identity_devices_key = f"{self.KEY_PREFIX}:identity:{identity_hash}:devices"
            interaction_count = self._redis.zscore(identity_devices_key, device_fingerprint)
            interaction_count = int(interaction_count) if interaction_count else 0

            # Get total devices for this identity
            all_devices = self._redis.zrange(identity_devices_key, 0, -1, withscores=True)
            other_device_count = max(0, len(all_devices) - 1) if all_devices else 0

            # Determine primary device (highest interaction count)
            primary_device = None
            max_interactions = 0
            if all_devices:
                for device, score in all_devices:
                    if score > max_interactions:
                        max_interactions = score
                        primary_device = device
            is_primary = primary_device == device_fingerprint

            # Get days associated
            meta_key = f"{self.KEY_PREFIX}:{identity_hash}:{device_fingerprint}:meta"
            meta = self._redis.hgetall(meta_key)
            days_associated = 0
            if meta and 'first_seen' in meta:
                first_seen = datetime.fromisoformat(meta['first_seen'])
                days_associated = (datetime.now() - first_seen).days

            # Calculate binding score (0-1)
            binding_score = self._calculate_binding_score(
                interaction_count=interaction_count,
                days_associated=days_associated,
                is_primary=is_primary,
                other_device_count=other_device_count,
            )

            # Calculate consistency score
            consistency_score = self._calculate_consistency_score(
                identity_hash, device_fingerprint
            )

            return BindingStrength(
                identity_hash=identity_hash,
                device_fingerprint=device_fingerprint,
                binding_score=binding_score,
                days_associated=days_associated,
                interaction_count=interaction_count,
                is_primary_device=is_primary,
                other_device_count=other_device_count,
                consistency_score=consistency_score,
            )

        except Exception as e:
            logger.warning(f"Failed to get binding strength: {e}")
            return BindingStrength(
                identity_hash=identity_hash,
                device_fingerprint=device_fingerprint,
                binding_score=0.0,
                days_associated=0,
                interaction_count=0,
                is_primary_device=False,
                other_device_count=0,
                consistency_score=0.0,
            )

    def _calculate_binding_score(
        self,
        interaction_count: int,
        days_associated: int,
        is_primary: bool,
        other_device_count: int,
    ) -> float:
        """Calculate binding score from factors."""
        score = 0.0

        # Interaction count factor (up to 0.4)
        score += min(0.4, interaction_count * 0.04)

        # Days associated factor (up to 0.3)
        score += min(0.3, days_associated * 0.01)

        # Primary device bonus
        if is_primary:
            score += 0.2

        # Penalty for many other devices
        if other_device_count > 5:
            score -= 0.1
        elif other_device_count > 10:
            score -= 0.2

        return max(0.0, min(1.0, score))

    def _calculate_consistency_score(
        self,
        identity_hash: str,
        device_fingerprint: str,
    ) -> float:
        """Calculate usage consistency score."""
        if not self._redis:
            return 0.0

        try:
            interactions_key = f"{self.KEY_PREFIX}:{identity_hash}:{device_fingerprint}:times"
            interactions = self._redis.zrange(interactions_key, 0, -1, withscores=True)

            if not interactions or len(interactions) < 2:
                return 0.5  # Neutral for insufficient data

            # Calculate regularity of interactions
            timestamps = sorted([score for _, score in interactions])
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]

            if not intervals:
                return 0.5

            avg_interval = sum(intervals) / len(intervals)
            if avg_interval == 0:
                return 1.0

            # Lower variance = higher consistency
            variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
            std_dev = variance ** 0.5

            # Normalize: std_dev of 0 = perfect consistency (1.0)
            # std_dev > avg_interval = low consistency
            consistency = max(0.0, 1.0 - (std_dev / (avg_interval + 1)))
            return consistency

        except Exception as e:
            logger.warning(f"Failed to calculate consistency: {e}")
            return 0.0

    def get_device_history(self, identity_hash: str) -> DeviceHistory:
        """
        Get device usage history for an identity.

        Args:
            identity_hash: Hash of the identity

        Returns:
            DeviceHistory
        """
        if not self._redis:
            return DeviceHistory(
                identity_hash=identity_hash,
                devices=[],
                primary_device=None,
                device_change_frequency=0.0,
                has_suspicious_pattern=False,
            )

        try:
            identity_devices_key = f"{self.KEY_PREFIX}:identity:{identity_hash}:devices"
            all_devices = self._redis.zrange(identity_devices_key, 0, -1, withscores=True)

            if not all_devices:
                return DeviceHistory(
                    identity_hash=identity_hash,
                    devices=[],
                    primary_device=None,
                    device_change_frequency=0.0,
                    has_suspicious_pattern=False,
                )

            devices = [device for device, _ in all_devices]

            # Find primary device
            primary_device = None
            max_score = 0
            for device, score in all_devices:
                if score > max_score:
                    max_score = score
                    primary_device = device

            # Calculate device change frequency
            device_change_frequency = self._calculate_change_frequency(identity_hash, devices)

            # Detect suspicious patterns
            has_suspicious = self._detect_suspicious_patterns(
                identity_hash, devices, device_change_frequency
            )

            return DeviceHistory(
                identity_hash=identity_hash,
                devices=devices,
                primary_device=primary_device,
                device_change_frequency=device_change_frequency,
                has_suspicious_pattern=has_suspicious,
            )

        except Exception as e:
            logger.warning(f"Failed to get device history: {e}")
            return DeviceHistory(
                identity_hash=identity_hash,
                devices=[],
                primary_device=None,
                device_change_frequency=0.0,
                has_suspicious_pattern=False,
            )

    def _calculate_change_frequency(
        self,
        identity_hash: str,
        devices: List[str],
    ) -> float:
        """Calculate device change frequency (changes per month)."""
        if len(devices) <= 1:
            return 0.0

        # Get first and last interaction times across all devices
        first_time = None
        last_time = None

        for device in devices:
            meta_key = f"{self.KEY_PREFIX}:{identity_hash}:{device}:meta"
            try:
                meta = self._redis.hgetall(meta_key) if self._redis else {}
                if meta:
                    if 'first_seen' in meta:
                        fs = datetime.fromisoformat(meta['first_seen'])
                        if first_time is None or fs < first_time:
                            first_time = fs
                    if 'last_seen' in meta:
                        ls = datetime.fromisoformat(meta['last_seen'])
                        if last_time is None or ls > last_time:
                            last_time = ls
            except Exception:
                pass

        if first_time is None or last_time is None:
            return 0.0

        months = max(1, (last_time - first_time).days / 30)
        return (len(devices) - 1) / months

    def _detect_suspicious_patterns(
        self,
        identity_hash: str,
        devices: List[str],
        change_frequency: float,
    ) -> bool:
        """Detect suspicious device usage patterns."""
        # High device change frequency
        if change_frequency > 3:  # More than 3 new devices per month
            return True

        # Too many devices
        if len(devices) > 10:
            return True

        return False

    def calculate_risk_score(
        self,
        identity_hash: str,
        current_device: str,
    ) -> float:
        """
        Calculate risk score based on device binding.

        Higher scores indicate weaker binding (more risk).

        Args:
            identity_hash: Hash of the identity
            current_device: Current device fingerprint

        Returns:
            Risk score (0-1)
        """
        binding = self.get_binding_strength(identity_hash, current_device)
        history = self.get_device_history(identity_hash)

        risk_score = 0.0

        # New device for this identity
        if binding.interaction_count == 0:
            risk_score += 0.3

        # Many devices associated with identity
        if history.device_change_frequency > 2:  # More than 2 changes per month
            risk_score += 0.3

        # Low binding score
        if binding.binding_score < 0.3:
            risk_score += 0.2

        # Suspicious patterns
        if history.has_suspicious_pattern:
            risk_score += 0.4

        return min(1.0, risk_score)

    def detect_device_sharing(
        self,
        device_fingerprint: str,
        min_identities: int = 3,
    ) -> Dict[str, Any]:
        """
        Detect if device is shared across multiple identities.

        Returns:
            dict with sharing analysis
        """
        if not self._redis:
            return {
                "is_shared": False,
                "identity_count": 0,
                "identity_hashes": [],
                "risk_score": 0.0,
            }

        try:
            device_identities_key = f"{self.KEY_PREFIX}:device:{device_fingerprint}:identities"
            identities = self._redis.zrange(device_identities_key, 0, -1)

            identity_count = len(identities) if identities else 0
            is_shared = identity_count >= min_identities

            # Calculate risk score based on sharing
            risk_score = 0.0
            if identity_count >= 10:
                risk_score = 1.0
            elif identity_count >= 5:
                risk_score = 0.7
            elif identity_count >= min_identities:
                risk_score = 0.4

            return {
                "is_shared": is_shared,
                "identity_count": identity_count,
                "identity_hashes": list(identities) if identities else [],
                "risk_score": risk_score,
            }

        except Exception as e:
            logger.warning(f"Failed to detect device sharing: {e}")
            return {
                "is_shared": False,
                "identity_count": 0,
                "identity_hashes": [],
                "risk_score": 0.0,
            }

    def detect_velocity_anomaly(
        self,
        identity_hash: str,
        window_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Detect abnormal device switching patterns.

        Returns:
            dict with anomaly analysis
        """
        if not self._redis:
            return {
                "has_anomaly": False,
                "device_count": 0,
                "anomaly_type": None,
                "risk_score": 0.0,
            }

        try:
            identity_devices_key = f"{self.KEY_PREFIX}:identity:{identity_hash}:devices"
            devices = self._redis.zrange(identity_devices_key, 0, -1)

            if not devices:
                return {
                    "has_anomaly": False,
                    "device_count": 0,
                    "anomaly_type": None,
                    "risk_score": 0.0,
                }

            # Get interactions within window
            cutoff = datetime.now() - timedelta(hours=window_hours)
            recent_devices = set()

            for device in devices:
                interactions_key = f"{self.KEY_PREFIX}:{identity_hash}:{device}:times"
                interactions = self._redis.zrangebyscore(
                    interactions_key, cutoff.timestamp(), "+inf"
                )
                if interactions:
                    recent_devices.add(device)

            device_count = len(recent_devices)

            # Detect anomalies
            anomaly_type = None
            risk_score = 0.0

            if device_count >= 5:
                anomaly_type = "excessive_device_switching"
                risk_score = 0.9
            elif device_count >= 3:
                anomaly_type = "high_device_switching"
                risk_score = 0.5

            return {
                "has_anomaly": anomaly_type is not None,
                "device_count": device_count,
                "anomaly_type": anomaly_type,
                "risk_score": risk_score,
            }

        except Exception as e:
            logger.warning(f"Failed to detect velocity anomaly: {e}")
            return {
                "has_anomaly": False,
                "device_count": 0,
                "anomaly_type": None,
                "risk_score": 0.0,
            }
