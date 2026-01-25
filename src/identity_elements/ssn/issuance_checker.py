"""SSN issuance year lookup and validation."""

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class IssuanceInfo:
    """SSN issuance information."""

    area_number: int
    estimated_year_start: Optional[int]
    estimated_year_end: Optional[int]
    state_issued: Optional[str]
    is_randomized_era: bool


class SSNIssuanceChecker:
    """Checks SSN issuance year against claimed DOB."""

    # Date when SSN randomization began
    RANDOMIZATION_START = date(2011, 6, 25)

    def __init__(self, area_year_mapping_path: Optional[str] = None):
        self._area_mapping: dict[int, IssuanceInfo] = {}
        if area_year_mapping_path:
            self._load_area_mapping(area_year_mapping_path)

    def _load_area_mapping(self, path: str) -> None:
        """Load area number to year mapping from CSV."""
        try:
            with open(path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    area = int(row["area_number"])
                    self._area_mapping[area] = IssuanceInfo(
                        area_number=area,
                        estimated_year_start=int(row["year_start"])
                        if row.get("year_start")
                        else None,
                        estimated_year_end=int(row["year_end"])
                        if row.get("year_end")
                        else None,
                        state_issued=row.get("state"),
                        is_randomized_era=False,
                    )
            logger.info(f"Loaded {len(self._area_mapping)} area mappings")
        except Exception as e:
            logger.error(f"Failed to load area mapping: {e}")

    def get_issuance_info(self, ssn_first3: str) -> Optional[IssuanceInfo]:
        """Get issuance information for SSN area number."""
        try:
            area = int(ssn_first3)
            return self._area_mapping.get(area)
        except ValueError:
            return None

    def check_ssn_dob_consistency(
        self,
        ssn_first3: str,
        dob: date,
        application_date: Optional[date] = None,
    ) -> dict:
        """
        Check if SSN issuance year is consistent with DOB.

        Returns dict with:
        - is_consistent: bool
        - mismatch_type: str if inconsistent
        - confidence: float
        - details: str
        """
        result = {
            "is_consistent": True,
            "mismatch_type": None,
            "confidence": 0.0,
            "details": "",
        }

        # Get issuance info
        issuance_info = self.get_issuance_info(ssn_first3)

        # If we don't have mapping data, we can't check
        if not issuance_info:
            result["details"] = "No issuance data available for area number"
            result["confidence"] = 0.0
            return result

        # If randomized era, we can't determine issuance year from area
        if issuance_info.is_randomized_era:
            result["details"] = "SSN from randomized era - cannot verify issuance"
            result["confidence"] = 0.0
            return result

        # Check if SSN was issued before person was born
        if issuance_info.estimated_year_end and dob.year > issuance_info.estimated_year_end:
            result["is_consistent"] = False
            result["mismatch_type"] = "ssn_before_birth"
            result["confidence"] = 0.95
            result["details"] = (
                f"SSN area issued before {issuance_info.estimated_year_end}, "
                f"but DOB is {dob.year}"
            )
            return result

        # Check if SSN was issued too long after birth (SSNs typically issued at birth now)
        if issuance_info.estimated_year_start:
            # After 1987, SSNs are typically issued at birth
            if dob.year >= 1987:
                expected_issuance_year = dob.year
                if issuance_info.estimated_year_start > expected_issuance_year + 5:
                    result["is_consistent"] = False
                    result["mismatch_type"] = "ssn_too_recent"
                    result["confidence"] = 0.7
                    result["details"] = (
                        f"SSN area not issued until {issuance_info.estimated_year_start}, "
                        f"but DOB is {dob.year} (post-1987 birth)"
                    )
                    return result

        result["details"] = "SSN issuance timing consistent with DOB"
        result["confidence"] = 0.8
        return result

    def calculate_mismatch_score(
        self, ssn_first3: str, dob: date
    ) -> float:
        """
        Calculate a mismatch score (0-1) for SSN-DOB consistency.

        Higher score = more likely mismatch/synthetic.
        """
        check_result = self.check_ssn_dob_consistency(ssn_first3, dob)

        if check_result["is_consistent"]:
            return 0.0

        # Weight by mismatch type and confidence
        mismatch_weights = {
            "ssn_before_birth": 1.0,  # Critical - impossible scenario
            "ssn_too_recent": 0.6,  # Suspicious but could be immigrant
        }

        mismatch_type = check_result["mismatch_type"]
        weight = mismatch_weights.get(mismatch_type, 0.5)

        return weight * check_result["confidence"]
