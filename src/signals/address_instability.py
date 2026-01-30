"""Address instability signal detection."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List


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

    def __init__(self, bureau_connector=None, address_velocity_tracker=None):
        self._bureau = bureau_connector
        self._velocity_tracker = address_velocity_tracker

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
        if self._bureau:
            try:
                credit_file = self._bureau.get_credit_file(ssn_hash)
                if credit_file and hasattr(credit_file, 'address_history'):
                    cutoff = datetime.now() - timedelta(days=months * 30)
                    changes = sum(
                        1 for addr in credit_file.address_history
                        if hasattr(addr, 'reported_date') and addr.reported_date >= cutoff
                    )
                    return max(0, changes - 1)  # Subtract 1 for current address
            except Exception:
                pass

        # Try velocity tracker as fallback
        if self._velocity_tracker:
            try:
                history = self._velocity_tracker.get_identity_addresses(ssn_hash)
                if history:
                    cutoff = datetime.now() - timedelta(days=months * 30)
                    recent = [h for h in history if h.get('first_seen', datetime.min) >= cutoff]
                    return len(recent)
            except Exception:
                pass

        return 0

    def _get_avg_address_tenure(self, ssn_hash: str) -> Optional[float]:
        """Get average address tenure in months."""
        if self._bureau:
            try:
                credit_file = self._bureau.get_credit_file(ssn_hash)
                if credit_file and hasattr(credit_file, 'address_history'):
                    addresses = credit_file.address_history
                    if len(addresses) >= 2:
                        tenures = []
                        sorted_addrs = sorted(
                            addresses,
                            key=lambda x: getattr(x, 'reported_date', datetime.min)
                        )
                        for i in range(len(sorted_addrs) - 1):
                            start = getattr(sorted_addrs[i], 'reported_date', None)
                            end = getattr(sorted_addrs[i + 1], 'reported_date', None)
                            if start and end:
                                tenure = (end - start).days / 30
                                tenures.append(tenure)
                        if tenures:
                            return sum(tenures) / len(tenures)
            except Exception:
                pass
        return None
