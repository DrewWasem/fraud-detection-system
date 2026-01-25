"""Post-2011 SSN randomization handling."""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RandomizationAnalysis:
    """Analysis of SSN in randomization context."""

    is_randomized_era: bool
    can_verify_state: bool
    high_group_valid: Optional[bool]
    analysis_notes: str


class SSNRandomization:
    """
    Handles SSN randomization that began June 25, 2011.

    After this date:
    - Area numbers are randomly assigned (not geographic)
    - Group numbers are randomly assigned
    - Traditional High Group validation no longer applies
    - Can no longer determine state of issuance from area
    """

    RANDOMIZATION_START = date(2011, 6, 25)

    def __init__(self, high_group_list_path: Optional[str] = None):
        """
        Initialize with optional High Group List for pre-randomization validation.

        Args:
            high_group_list_path: Path to SSA High Group List file
        """
        self._high_group_list: dict[int, int] = {}
        if high_group_list_path:
            self._load_high_group_list(high_group_list_path)

    def _load_high_group_list(self, path: str) -> None:
        """Load SSA High Group List."""
        # TODO: Implement parsing of High Group List
        # Format varies - typically area -> highest group issued
        logger.info(f"Loading High Group List from {path}")

    def is_randomization_era(self, issuance_date: date) -> bool:
        """Check if date falls in randomization era."""
        return issuance_date >= self.RANDOMIZATION_START

    def analyze_ssn(
        self,
        area: int,
        group: int,
        claimed_issuance_date: Optional[date] = None,
    ) -> RandomizationAnalysis:
        """
        Analyze SSN considering randomization.

        Args:
            area: SSN area number (first 3 digits)
            group: SSN group number (middle 2 digits)
            claimed_issuance_date: Claimed date of SSN issuance

        Returns:
            RandomizationAnalysis with findings
        """
        # If we have a claimed issuance date, use it
        if claimed_issuance_date:
            is_randomized = self.is_randomization_era(claimed_issuance_date)
        else:
            # Without date, we can't definitively determine
            is_randomized = None

        # Pre-randomization: can verify against High Group List
        if is_randomized is False and self._high_group_list:
            max_group = self._high_group_list.get(area)
            if max_group is not None:
                # Check if group exceeds what was issued
                high_group_valid = self._is_group_valid(group, max_group)
                return RandomizationAnalysis(
                    is_randomized_era=False,
                    can_verify_state=True,
                    high_group_valid=high_group_valid,
                    analysis_notes=(
                        f"Pre-randomization SSN. Group {group} "
                        f"{'valid' if high_group_valid else 'exceeds'} "
                        f"High Group {max_group} for area {area}"
                    ),
                )

        if is_randomized is True:
            return RandomizationAnalysis(
                is_randomized_era=True,
                can_verify_state=False,
                high_group_valid=None,
                analysis_notes=(
                    "Post-randomization SSN. Cannot verify geographic origin "
                    "or use High Group validation."
                ),
            )

        return RandomizationAnalysis(
            is_randomized_era=is_randomized,
            can_verify_state=is_randomized is False,
            high_group_valid=None,
            analysis_notes="Unable to determine randomization era without issuance date",
        )

    def _is_group_valid(self, group: int, max_group: int) -> bool:
        """
        Check if group number is valid given the max issued group.

        SSA issues groups in a specific order:
        Odd numbers 01-09, then even 10-98, then even 02-08, then odd 11-99
        """
        # Simplified check - in practice would need full group order logic
        return group <= max_group

    def get_randomization_risk_score(
        self,
        area: int,
        group: int,
        dob: date,
    ) -> float:
        """
        Calculate risk score based on randomization patterns.

        Synthetic identities may exploit randomization by using
        area numbers that wouldn't match their claimed location/age.
        """
        # If person was born before randomization but has
        # SSN that can't be verified, that's suspicious
        if dob < self.RANDOMIZATION_START:
            analysis = self.analyze_ssn(area, group)
            if analysis.high_group_valid is False:
                return 0.8  # High risk - group exceeds what was issued
            if analysis.can_verify_state is False:
                return 0.3  # Medium risk - can't verify pre-randomization SSN

        return 0.0
