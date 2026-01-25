"""SSN validation rules and checks."""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SSNValidationResult(Enum):
    """SSN validation status."""

    VALID = "valid"
    INVALID_FORMAT = "invalid_format"
    INVALID_AREA = "invalid_area"
    INVALID_GROUP = "invalid_group"
    ITIN = "itin"
    ADVERTISING = "advertising"
    DEATH_MASTER = "death_master"


@dataclass
class SSNValidation:
    """SSN validation result."""

    result: SSNValidationResult
    area_number: Optional[int]
    group_number: Optional[int]
    serial_number: Optional[int]
    is_randomized: bool
    message: str


class SSNValidator:
    """Validates Social Security Numbers."""

    # Invalid area numbers (never issued)
    INVALID_AREAS = {0, 666} | set(range(900, 1000))

    # Advertising range (used in commercials)
    ADVERTISING_AREAS = set(range(987, 988))
    ADVERTISING_GROUPS = {65}
    ADVERTISING_SERIALS = set(range(4320, 4330))

    # SSN pattern
    SSN_PATTERN = re.compile(r"^(\d{3})-?(\d{2})-?(\d{4})$")

    def __init__(self, death_master_file_path: Optional[str] = None):
        self.death_master_ssns: set[str] = set()
        if death_master_file_path:
            self._load_death_master_file(death_master_file_path)

    def _load_death_master_file(self, path: str) -> None:
        """Load Death Master File SSN hashes."""
        # TODO: Implement loading from DMF
        logger.info(f"Loading Death Master File from {path}")

    def validate(self, ssn: str) -> SSNValidation:
        """Validate an SSN."""
        # Clean the SSN
        ssn_clean = ssn.replace("-", "").replace(" ", "")

        # Check format
        match = self.SSN_PATTERN.match(ssn)
        if not match:
            return SSNValidation(
                result=SSNValidationResult.INVALID_FORMAT,
                area_number=None,
                group_number=None,
                serial_number=None,
                is_randomized=False,
                message="SSN does not match expected format",
            )

        area = int(match.group(1))
        group = int(match.group(2))
        serial = int(match.group(3))

        # Check for ITIN (Individual Taxpayer Identification Number)
        if 900 <= area <= 999:
            return SSNValidation(
                result=SSNValidationResult.ITIN,
                area_number=area,
                group_number=group,
                serial_number=serial,
                is_randomized=False,
                message="Number is an ITIN, not an SSN",
            )

        # Check invalid areas
        if area in self.INVALID_AREAS:
            return SSNValidation(
                result=SSNValidationResult.INVALID_AREA,
                area_number=area,
                group_number=group,
                serial_number=serial,
                is_randomized=False,
                message=f"Area number {area} is not valid",
            )

        # Check for zero group or serial
        if group == 0:
            return SSNValidation(
                result=SSNValidationResult.INVALID_GROUP,
                area_number=area,
                group_number=group,
                serial_number=serial,
                is_randomized=False,
                message="Group number cannot be 00",
            )

        if serial == 0:
            return SSNValidation(
                result=SSNValidationResult.INVALID_FORMAT,
                area_number=area,
                group_number=group,
                serial_number=serial,
                is_randomized=False,
                message="Serial number cannot be 0000",
            )

        # Check advertising SSNs
        if (
            area in self.ADVERTISING_AREAS
            and group in self.ADVERTISING_GROUPS
            and serial in self.ADVERTISING_SERIALS
        ):
            return SSNValidation(
                result=SSNValidationResult.ADVERTISING,
                area_number=area,
                group_number=group,
                serial_number=serial,
                is_randomized=False,
                message="SSN is in advertising range (used in commercials)",
            )

        # Check Death Master File
        if ssn_clean in self.death_master_ssns:
            return SSNValidation(
                result=SSNValidationResult.DEATH_MASTER,
                area_number=area,
                group_number=group,
                serial_number=serial,
                is_randomized=False,
                message="SSN appears in Death Master File",
            )

        # Determine if randomized (post June 25, 2011)
        # After randomization, we can't determine issuance from area
        is_randomized = self._check_if_randomized(area, group)

        return SSNValidation(
            result=SSNValidationResult.VALID,
            area_number=area,
            group_number=group,
            serial_number=serial,
            is_randomized=is_randomized,
            message="SSN format is valid",
        )

    def _check_if_randomized(self, area: int, group: int) -> bool:
        """Heuristic to check if SSN might be from randomized era."""
        # This is a simplified check - actual determination requires
        # checking against High Group List
        # For now, assume we can't definitively determine
        return False

    def is_valid(self, ssn: str) -> bool:
        """Quick check if SSN is valid."""
        result = self.validate(ssn)
        return result.result == SSNValidationResult.VALID
