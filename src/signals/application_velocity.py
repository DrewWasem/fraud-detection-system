"""Application velocity signal detection."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


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
        # TODO: Implement Redis lookup
        return 0

    def _get_unique_institutions(self, ssn_hash: str, days: int) -> int:
        """Get unique institution count."""
        # TODO: Implement Redis lookup
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
        # TODO: Implement Redis storage
