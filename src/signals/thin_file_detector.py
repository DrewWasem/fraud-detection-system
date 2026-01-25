"""Thin credit file detection signal."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ThinFileResult:
    """Thin file detection result."""

    is_thin_file: bool
    tradeline_count: int
    file_age_months: Optional[int]
    severity: str
    score_impact: float
    details: str


class ThinFileSignal:
    """Detects thin credit files that may indicate synthetic identities."""

    MIN_TRADELINES = 3
    MIN_FILE_AGE_MONTHS = 24

    def __init__(self, bureau_connector=None):
        self._bureau = bureau_connector

    def detect(
        self,
        ssn_hash: str,
        claimed_dob: datetime,
    ) -> ThinFileResult:
        """
        Detect thin file signal.

        Args:
            ssn_hash: Hashed SSN
            claimed_dob: Claimed date of birth

        Returns:
            ThinFileResult with detection findings
        """
        # Get credit file info
        tradeline_count = self._get_tradeline_count(ssn_hash)
        file_age = self._get_file_age(ssn_hash)

        is_thin = tradeline_count < self.MIN_TRADELINES

        # Calculate claimed age
        claimed_age_years = (datetime.now() - claimed_dob).days / 365

        # Determine severity
        if is_thin and claimed_age_years > 35:
            severity = "high"
            score_impact = 0.35
            details = f"Thin file ({tradeline_count} tradelines) for {int(claimed_age_years)}-year-old"
        elif is_thin and claimed_age_years > 25:
            severity = "medium"
            score_impact = 0.20
            details = f"Thin file ({tradeline_count} tradelines) for adult identity"
        elif is_thin:
            severity = "low"
            score_impact = 0.10
            details = f"Thin file ({tradeline_count} tradelines)"
        else:
            severity = "none"
            score_impact = 0.0
            details = "Normal credit file"

        return ThinFileResult(
            is_thin_file=is_thin,
            tradeline_count=tradeline_count,
            file_age_months=file_age,
            severity=severity,
            score_impact=score_impact,
            details=details,
        )

    def _get_tradeline_count(self, ssn_hash: str) -> int:
        """Get tradeline count from bureau."""
        if self._bureau:
            credit_file = self._bureau.get_credit_file(ssn_hash)
            if credit_file:
                return credit_file.num_tradelines
        return 0

    def _get_file_age(self, ssn_hash: str) -> Optional[int]:
        """Get file age in months."""
        if self._bureau:
            return self._bureau.get_credit_file_age(ssn_hash)
        return None
