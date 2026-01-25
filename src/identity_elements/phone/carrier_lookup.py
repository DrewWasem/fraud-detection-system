"""Phone carrier and line type lookup."""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class LineType(Enum):
    """Phone line types."""

    MOBILE = "mobile"
    LANDLINE = "landline"
    VOIP = "voip"
    TOLL_FREE = "toll_free"
    PREMIUM = "premium"
    UNKNOWN = "unknown"


@dataclass
class CarrierInfo:
    """Carrier lookup result."""

    phone_number: str
    carrier_name: Optional[str]
    line_type: LineType
    country_code: str
    is_valid: bool
    is_ported: bool
    original_carrier: Optional[str]
    risk_score: float


class CarrierLookup:
    """Lookup phone carrier and line type information."""

    # Toll-free prefixes
    TOLL_FREE_PREFIXES = {"800", "888", "877", "866", "855", "844", "833"}

    # Premium rate prefixes
    PREMIUM_PREFIXES = {"900", "976"}

    def __init__(self, api_key: Optional[str] = None, provider: str = "default"):
        """
        Initialize carrier lookup.

        Args:
            api_key: API key for carrier lookup service
            provider: Service provider name
        """
        self.api_key = api_key
        self.provider = provider

    def lookup(self, phone_number: str) -> CarrierInfo:
        """
        Look up carrier information for a phone number.

        Args:
            phone_number: Phone number to look up

        Returns:
            CarrierInfo with carrier details
        """
        # Normalize phone number
        normalized = self._normalize(phone_number)

        if not normalized:
            return CarrierInfo(
                phone_number=phone_number,
                carrier_name=None,
                line_type=LineType.UNKNOWN,
                country_code="",
                is_valid=False,
                is_ported=False,
                original_carrier=None,
                risk_score=0.5,
            )

        # Check special prefixes
        area_code = normalized[0:3]

        if area_code in self.TOLL_FREE_PREFIXES:
            return CarrierInfo(
                phone_number=normalized,
                carrier_name="Toll-Free",
                line_type=LineType.TOLL_FREE,
                country_code="1",
                is_valid=True,
                is_ported=False,
                original_carrier=None,
                risk_score=0.8,  # High risk for toll-free
            )

        if area_code in self.PREMIUM_PREFIXES:
            return CarrierInfo(
                phone_number=normalized,
                carrier_name="Premium",
                line_type=LineType.PREMIUM,
                country_code="1",
                is_valid=True,
                is_ported=False,
                original_carrier=None,
                risk_score=0.9,  # Very high risk for premium
            )

        # TODO: Implement actual carrier API lookup
        # For now, return placeholder
        return CarrierInfo(
            phone_number=normalized,
            carrier_name=None,
            line_type=LineType.UNKNOWN,
            country_code="1",
            is_valid=True,
            is_ported=False,
            original_carrier=None,
            risk_score=0.0,
        )

    def _normalize(self, phone_number: str) -> Optional[str]:
        """Normalize phone number to 10 digits (US)."""
        # Remove all non-digits
        digits = re.sub(r"\D", "", phone_number)

        # Handle country code
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        # Validate length
        if len(digits) != 10:
            return None

        return digits

    def get_risk_score(self, info: CarrierInfo) -> float:
        """Calculate risk score based on carrier info."""
        score = info.risk_score

        # VoIP numbers are higher risk
        if info.line_type == LineType.VOIP:
            score = max(score, 0.6)

        # Ported numbers slightly higher risk
        if info.is_ported:
            score += 0.1

        # Unknown carrier is suspicious
        if info.carrier_name is None and info.is_valid:
            score += 0.2

        return min(1.0, score)
