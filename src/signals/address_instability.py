"""Address instability signal detection."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AddressInstabilityResult:
    """Address instability detection result."""

    is_unstable: bool
    address_changes_12m: int
    address_changes_24m: int
    avg_tenure_months: float
    severity: str
    score_impact: float
    details: str


class AddressInstabilitySignal:
    """Detects address instability patterns."""

    # Thresholds
    MAX_CHANGES_12M = 2
    MAX_CHANGES_24M = 4
    MIN_AVG_TENURE = 6  # months

    def __init__(self, bureau_connector=None):
        self._bureau = bureau_connector

    def detect(
        self,
        ssn_hash: str,
    ) -> AddressInstabilityResult:
        """
        Detect address instability signal.

        Args:
            ssn_hash: Hashed SSN

        Returns:
            AddressInstabilityResult with findings
        """
        # Get address history
        changes_12m = self._get_address_changes(ssn_hash, months=12)
        changes_24m = self._get_address_changes(ssn_hash, months=24)
        avg_tenure = self._get_avg_address_tenure(ssn_hash)

        # Determine if unstable
        is_unstable = (
            changes_12m > self.MAX_CHANGES_12M or
            changes_24m > self.MAX_CHANGES_24M or
            (avg_tenure is not None and avg_tenure < self.MIN_AVG_TENURE)
        )

        # Determine severity
        if changes_12m > self.MAX_CHANGES_12M * 2:
            severity = "high"
            score_impact = 0.25
        elif is_unstable:
            severity = "medium"
            score_impact = 0.15
        else:
            severity = "none"
            score_impact = 0.0

        details = (
            f"{changes_12m} changes (12m), {changes_24m} changes (24m), "
            f"avg tenure {avg_tenure or 'unknown'} months"
        )

        return AddressInstabilityResult(
            is_unstable=is_unstable,
            address_changes_12m=changes_12m,
            address_changes_24m=changes_24m,
            avg_tenure_months=avg_tenure or 0.0,
            severity=severity,
            score_impact=score_impact,
            details=details,
        )

    def _get_address_changes(self, ssn_hash: str, months: int) -> int:
        """Get address change count for period."""
        # TODO: Implement bureau query
        return 0

    def _get_avg_address_tenure(self, ssn_hash: str) -> Optional[float]:
        """Get average address tenure in months."""
        # TODO: Implement bureau query
        return None
