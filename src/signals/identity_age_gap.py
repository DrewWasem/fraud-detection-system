"""Identity vs credit file age gap signal."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AgeGapResult:
    """Age gap detection result."""

    has_gap: bool
    claimed_age_years: float
    file_age_months: Optional[int]
    expected_file_age_months: float
    gap_months: float
    severity: str
    score_impact: float
    details: str


class IdentityAgeGapSignal:
    """Detects gaps between claimed identity age and credit file age."""

    def __init__(self, bureau_connector=None):
        self._bureau = bureau_connector

    def detect(
        self,
        ssn_hash: str,
        claimed_dob: datetime,
    ) -> AgeGapResult:
        """
        Detect identity age gap signal.

        Args:
            ssn_hash: Hashed SSN
            claimed_dob: Claimed date of birth

        Returns:
            AgeGapResult with findings
        """
        # Calculate claimed age
        claimed_age_years = (datetime.now() - claimed_dob).days / 365

        # Get actual file age
        file_age = self._get_file_age(ssn_hash)

        # Expected file age (credit file should exist since age 18)
        expected_file_age = max(0, (claimed_age_years - 18) * 12)

        if file_age is None:
            return AgeGapResult(
                has_gap=False,
                claimed_age_years=claimed_age_years,
                file_age_months=None,
                expected_file_age_months=expected_file_age,
                gap_months=0,
                severity="unknown",
                score_impact=0.0,
                details="Unable to determine credit file age",
            )

        # Calculate gap
        gap_months = expected_file_age - file_age

        # Determine if significant gap
        if gap_months > 60:  # 5+ year gap
            severity = "critical"
            score_impact = 0.45
            has_gap = True
        elif gap_months > 36:  # 3+ year gap
            severity = "high"
            score_impact = 0.30
            has_gap = True
        elif gap_months > 12:  # 1+ year gap
            severity = "medium"
            score_impact = 0.15
            has_gap = True
        else:
            severity = "none"
            score_impact = 0.0
            has_gap = False

        details = (
            f"Claimed age {int(claimed_age_years)}, file age {file_age} months "
            f"(expected ~{int(expected_file_age)} months)"
        )

        return AgeGapResult(
            has_gap=has_gap,
            claimed_age_years=claimed_age_years,
            file_age_months=file_age,
            expected_file_age_months=expected_file_age,
            gap_months=gap_months,
            severity=severity,
            score_impact=score_impact,
            details=details,
        )

    def _get_file_age(self, ssn_hash: str) -> Optional[int]:
        """Get credit file age in months."""
        if self._bureau:
            return self._bureau.get_credit_file_age(ssn_hash)
        return None
