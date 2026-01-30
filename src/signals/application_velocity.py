"""Application velocity signal detection."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Set


@dataclass
class ApplicationVelocityResult:
    """Application velocity detection result."""

    is_high_velocity: bool
    applications_7d: int
    applications_30d: int
    applications_90d: int
    unique_institutions_30d: int
    severity: str
    score_impact: float
    details: str


class ApplicationVelocitySignal:
    """Detects high application velocity patterns."""

    # Thresholds
    MAX_APPS_7D = 3
    MAX_APPS_30D = 6
    MAX_APPS_90D = 12

    # Redis key prefix
    KEY_PREFIX = "app_velocity"
    TTL_DAYS = 90

    def __init__(self, redis_client=None):
        self._redis = redis_client

    def detect(
        self,
        identity_hash: str,
        ssn_hash: str,
    ) -> ApplicationVelocityResult:
        """
        Detect application velocity signal.

        Args:
            identity_hash: Hash of the identity
            ssn_hash: Hashed SSN

        Returns:
            ApplicationVelocityResult with findings
        """
        # Get application counts
        apps_7d = self._get_app_count(ssn_hash, days=7)
        apps_30d = self._get_app_count(ssn_hash, days=30)
        apps_90d = self._get_app_count(ssn_hash, days=90)
        unique_institutions = self._get_unique_institutions(ssn_hash, days=30)

        # Determine if high velocity
        is_high = (
            apps_7d > self.MAX_APPS_7D or
            apps_30d > self.MAX_APPS_30D or
            apps_90d > self.MAX_APPS_90D
        )

        # Determine severity
        if apps_7d > self.MAX_APPS_7D * 2:
            severity = "critical"
            score_impact = 0.40
        elif apps_7d > self.MAX_APPS_7D or apps_30d > self.MAX_APPS_30D * 1.5:
            severity = "high"
            score_impact = 0.30
        elif is_high:
            severity = "medium"
            score_impact = 0.20
        else:
            severity = "none"
            score_impact = 0.0

        details = (
            f"{apps_7d} apps (7d), {apps_30d} apps (30d), "
            f"{unique_institutions} unique institutions"
        )

        return ApplicationVelocityResult(
            is_high_velocity=is_high,
            applications_7d=apps_7d,
            applications_30d=apps_30d,
            applications_90d=apps_90d,
            unique_institutions_30d=unique_institutions,
            severity=severity,
            score_impact=score_impact,
            details=details,
        )

    def _get_app_count(self, ssn_hash: str, days: int) -> int:
        """Get application count for time period."""
        if not self._redis:
            return 0

        try:
            key = f"{self.KEY_PREFIX}:{ssn_hash}:apps"
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = cutoff.timestamp()

            # Use sorted set with timestamps as scores
            count = self._redis.zcount(key, cutoff_ts, "+inf")
            return count or 0
        except Exception:
            return 0

    def _get_unique_institutions(self, ssn_hash: str, days: int) -> int:
        """Get unique institution count."""
        if not self._redis:
            return 0

        try:
            key = f"{self.KEY_PREFIX}:{ssn_hash}:apps"
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = cutoff.timestamp()

            # Get all applications in range
            apps = self._redis.zrangebyscore(key, cutoff_ts, "+inf")
            if not apps:
                return 0

            # Extract unique institutions
            institutions: Set[str] = set()
            for app_data in apps:
                try:
                    data = json.loads(app_data)
                    if 'institution_id' in data:
                        institutions.add(data['institution_id'])
                except (json.JSONDecodeError, TypeError):
                    pass

            return len(institutions)
        except Exception:
            return 0

    def record_application(
        self,
        ssn_hash: str,
        institution_id: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a new application."""
        if timestamp is None:
            timestamp = datetime.now()

        if not self._redis:
            return

        try:
            key = f"{self.KEY_PREFIX}:{ssn_hash}:apps"
            app_data = json.dumps({
                'institution_id': institution_id,
                'timestamp': timestamp.isoformat(),
            })

            # Add to sorted set with timestamp as score
            self._redis.zadd(key, {app_data: timestamp.timestamp()})

            # Set TTL
            self._redis.expire(key, self.TTL_DAYS * 24 * 60 * 60)

            # Clean old entries
            cutoff = datetime.now() - timedelta(days=self.TTL_DAYS)
            self._redis.zremrangebyscore(key, "-inf", cutoff.timestamp())
        except Exception:
            pass

    def get_application_history(
        self,
        ssn_hash: str,
        days: int = 90,
    ) -> List[dict]:
        """Get application history for an identity."""
        if not self._redis:
            return []

        try:
            key = f"{self.KEY_PREFIX}:{ssn_hash}:apps"
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = cutoff.timestamp()

            apps = self._redis.zrangebyscore(key, cutoff_ts, "+inf", withscores=True)
            if not apps:
                return []

            history = []
            for app_data, score in apps:
                try:
                    data = json.loads(app_data)
                    data['score_timestamp'] = score
                    history.append(data)
                except (json.JSONDecodeError, TypeError):
                    pass

            return sorted(history, key=lambda x: x.get('score_timestamp', 0), reverse=True)
        except Exception:
            return []
