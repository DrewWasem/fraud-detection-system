"""SSN-DOB mismatch signal detection."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.identity_elements.ssn import SSNIssuanceChecker


@dataclass
class MismatchResult:
    """SSN-DOB mismatch detection result."""

    is_mismatch: bool
    severity: str  # critical, high, medium, low
    mismatch_type: Optional[str]
    score_impact: float
    details: str


class SSNDOBMismatchSignal:
    """Detects inconsistencies between SSN issuance and claimed DOB."""

    def __init__(self, issuance_checker: Optional[SSNIssuanceChecker] = None):
        self._checker = issuance_checker or SSNIssuanceChecker()

    def detect(self, ssn_first3: str, dob: date) -> MismatchResult:
        """
        Detect SSN-DOB mismatch.

        Args:
            ssn_first3: First 3 digits of SSN (area number)
            dob: Claimed date of birth

        Returns:
            MismatchResult with detection findings
        """
        check = self._checker.check_ssn_dob_consistency(ssn_first3, dob)

        if check["is_consistent"]:
            return MismatchResult(
                is_mismatch=False,
                severity="none",
                mismatch_type=None,
                score_impact=0.0,
                details="SSN issuance consistent with DOB",
            )

        # Determine severity based on mismatch type
        mismatch_type = check.get("mismatch_type")

        if mismatch_type == "ssn_before_birth":
            severity = "critical"
            score_impact = 0.40
        elif mismatch_type == "ssn_too_recent":
            severity = "high"
            score_impact = 0.25
        else:
            severity = "medium"
            score_impact = 0.15

        return MismatchResult(
            is_mismatch=True,
            severity=severity,
            mismatch_type=mismatch_type,
            score_impact=score_impact,
            details=check.get("details", "SSN-DOB mismatch detected"),
        )
