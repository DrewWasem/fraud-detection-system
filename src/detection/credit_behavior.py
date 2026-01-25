"""Credit behavior analysis for synthetic identity detection."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CreditBehaviorAnalysis:
    """Credit behavior analysis result."""

    identity_id: str
    is_thin_file: bool
    file_age_months: Optional[int]
    num_tradelines: int
    num_authorized_user_accounts: int
    au_to_primary_ratio: float
    credit_building_velocity: float
    behavior_score: float
    anomalies: list[str]


class CreditBehaviorAnalyzer:
    """Analyzes credit behavior patterns for synthetic identity detection."""

    def __init__(self, bureau_connector=None):
        """
        Initialize analyzer.

        Args:
            bureau_connector: Credit bureau connector
        """
        self._bureau = bureau_connector

    def analyze(
        self,
        identity_id: str,
        ssn_hash: str,
        claimed_dob: datetime,
    ) -> CreditBehaviorAnalysis:
        """
        Analyze credit behavior for an identity.

        Args:
            identity_id: Identity to analyze
            ssn_hash: Hashed SSN
            claimed_dob: Claimed date of birth

        Returns:
            CreditBehaviorAnalysis with findings
        """
        anomalies = []

        # Get credit file info (placeholder if no bureau connection)
        file_age_months = self._get_file_age(ssn_hash)
        num_tradelines = self._get_tradeline_count(ssn_hash)
        au_accounts = self._get_au_account_count(ssn_hash)

        # Determine if thin file
        is_thin_file = num_tradelines < 3

        # Calculate AU ratio
        primary_accounts = max(0, num_tradelines - au_accounts)
        au_ratio = au_accounts / num_tradelines if num_tradelines > 0 else 0.0

        # Check for file age vs claimed age mismatch
        claimed_age_years = (datetime.now() - claimed_dob).days / 365
        if file_age_months is not None:
            expected_min_file_age = max(0, (claimed_age_years - 18) * 12)
            if file_age_months < expected_min_file_age * 0.3:
                anomalies.append("FILE_AGE_MISMATCH")

        # Check for thin file with old claimed age
        if is_thin_file and claimed_age_years > 30:
            anomalies.append("THIN_FILE_OLD_IDENTITY")

        # Check AU abuse patterns
        if au_ratio > 0.6 and au_accounts >= 3:
            anomalies.append("AU_ABUSE_PATTERN")

        # Check credit building velocity
        credit_velocity = self._calculate_credit_velocity(ssn_hash)
        if credit_velocity > 0.7:
            anomalies.append("RAPID_CREDIT_BUILDING")

        # Calculate overall behavior score
        behavior_score = self._calculate_behavior_score(
            is_thin_file,
            file_age_months,
            au_ratio,
            credit_velocity,
            anomalies,
            claimed_age_years,
        )

        return CreditBehaviorAnalysis(
            identity_id=identity_id,
            is_thin_file=is_thin_file,
            file_age_months=file_age_months,
            num_tradelines=num_tradelines,
            num_authorized_user_accounts=au_accounts,
            au_to_primary_ratio=au_ratio,
            credit_building_velocity=credit_velocity,
            behavior_score=behavior_score,
            anomalies=anomalies,
        )

    def _get_file_age(self, ssn_hash: str) -> Optional[int]:
        """Get credit file age in months."""
        if self._bureau:
            return self._bureau.get_credit_file_age(ssn_hash)
        return None

    def _get_tradeline_count(self, ssn_hash: str) -> int:
        """Get number of tradelines."""
        if self._bureau:
            credit_file = self._bureau.get_credit_file(ssn_hash)
            if credit_file:
                return credit_file.num_tradelines
        return 0

    def _get_au_account_count(self, ssn_hash: str) -> int:
        """Get number of authorized user accounts."""
        if self._bureau:
            return self._bureau.get_authorized_user_count(ssn_hash)
        return 0

    def _calculate_credit_velocity(self, ssn_hash: str) -> float:
        """
        Calculate how fast credit is being built.

        Synthetic identities often show unnaturally fast credit building.
        """
        # TODO: Implement actual calculation based on:
        # - Rate of new tradeline additions
        # - Credit limit growth rate
        # - Score improvement velocity
        return 0.0

    def _calculate_behavior_score(
        self,
        is_thin_file: bool,
        file_age_months: Optional[int],
        au_ratio: float,
        credit_velocity: float,
        anomalies: list[str],
        claimed_age_years: float,
    ) -> float:
        """Calculate overall suspicious behavior score."""
        score = 0.0

        # Thin file is somewhat suspicious
        if is_thin_file:
            score += 0.2

        # Thin file with old claimed age is very suspicious
        if is_thin_file and claimed_age_years > 35:
            score += 0.3

        # High AU ratio
        if au_ratio > 0.5:
            score += au_ratio * 0.4

        # Rapid credit building
        score += credit_velocity * 0.3

        # File age mismatch
        if "FILE_AGE_MISMATCH" in anomalies:
            score += 0.4

        return min(1.0, score)

    def check_credit_file_age_consistency(
        self,
        ssn_hash: str,
        claimed_dob: datetime,
    ) -> dict:
        """
        Check if credit file age is consistent with claimed identity.

        Returns:
            dict with is_consistent, expected_age, actual_age, gap
        """
        file_age_months = self._get_file_age(ssn_hash)
        if file_age_months is None:
            return {
                "is_consistent": None,
                "expected_age_months": None,
                "actual_age_months": None,
                "gap_months": None,
                "message": "Unable to determine file age",
            }

        claimed_age_years = (datetime.now() - claimed_dob).days / 365

        # Expected: credit file should exist since age 18
        expected_file_age = max(0, (claimed_age_years - 18) * 12)

        gap = expected_file_age - file_age_months

        # Allow some tolerance
        is_consistent = gap < 24  # Less than 2 year gap is acceptable

        return {
            "is_consistent": is_consistent,
            "expected_age_months": expected_file_age,
            "actual_age_months": file_age_months,
            "gap_months": gap,
            "message": (
                "File age consistent with claimed identity"
                if is_consistent
                else f"File {int(gap)} months younger than expected"
            ),
        }
