"""Score addresses for residential vs commercial use."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AddressType(Enum):
    """Types of addresses."""

    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    PO_BOX = "po_box"
    CMRA = "cmra"  # Commercial Mail Receiving Agency (UPS Store, etc.)
    PRISON = "prison"
    VACANT = "vacant"
    UNKNOWN = "unknown"


@dataclass
class ResidentialScore:
    """Residential scoring result."""

    address_hash: str
    address_type: AddressType
    residential_probability: float
    is_cmra: bool
    is_high_risk_location: bool
    dwelling_type: Optional[str]  # single_family, apartment, etc.
    notes: str


class ResidentialScorer:
    """Scores addresses for residential legitimacy."""

    # Known CMRA chains
    CMRA_INDICATORS = [
        "ups store",
        "mailboxes etc",
        "postal connections",
        "postnet",
        "mail center",
        "pack & ship",
        "postal annex",
    ]

    # High-risk location patterns
    HIGH_RISK_PATTERNS = [
        "homeless shelter",
        "halfway house",
        "motel",
        "hotel",
        "extended stay",
        "correctional",
        "detention",
    ]

    def __init__(self, address_database_path: Optional[str] = None):
        """
        Initialize scorer.

        Args:
            address_database_path: Path to address validation database
        """
        self._db_path = address_database_path
        # TODO: Load address database

    def score(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
    ) -> ResidentialScore:
        """
        Score an address for residential legitimacy.

        Args:
            street: Street address
            city: City name
            state: State code
            zip_code: ZIP code

        Returns:
            ResidentialScore with analysis
        """
        # Generate hash for caching
        from src.identity_elements.address.normalizer import AddressNormalizer

        normalizer = AddressNormalizer()
        normalized = normalizer.normalize(street, city, state, zip_code)
        address_hash = normalized.normalized_hash

        # Check for CMRA
        is_cmra = self._check_cmra(street)

        # Check for high-risk locations
        is_high_risk = self._check_high_risk(street)

        # Determine address type
        address_type, probability = self._determine_type(
            street, city, state, zip_code, is_cmra
        )

        # Determine dwelling type
        dwelling_type = self._get_dwelling_type(street)

        notes = []
        if is_cmra:
            notes.append("Address appears to be a CMRA/mail drop")
        if is_high_risk:
            notes.append("Address matches high-risk location pattern")
        if address_type == AddressType.PO_BOX:
            notes.append("PO Box address")

        return ResidentialScore(
            address_hash=address_hash,
            address_type=address_type,
            residential_probability=probability,
            is_cmra=is_cmra,
            is_high_risk_location=is_high_risk,
            dwelling_type=dwelling_type,
            notes="; ".join(notes) if notes else "Standard residential address",
        )

    def _check_cmra(self, street: str) -> bool:
        """Check if address is a Commercial Mail Receiving Agency."""
        street_lower = street.lower()

        # Check for CMRA chain names
        for indicator in self.CMRA_INDICATORS:
            if indicator in street_lower:
                return True

        # Check for PMB (Private Mail Box) indicator
        if "pmb" in street_lower or "private mail" in street_lower:
            return True

        # Check for suspicious unit patterns (common at CMRAs)
        # e.g., "#1234" where the number is unusually high
        import re

        unit_match = re.search(r"#\s*(\d+)", street_lower)
        if unit_match:
            unit_num = int(unit_match.group(1))
            if unit_num > 500:  # Unusually high unit number
                return True

        return False

    def _check_high_risk(self, street: str) -> bool:
        """Check if address matches high-risk patterns."""
        street_lower = street.lower()
        for pattern in self.HIGH_RISK_PATTERNS:
            if pattern in street_lower:
                return True
        return False

    def _determine_type(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        is_cmra: bool,
    ) -> tuple[AddressType, float]:
        """Determine address type and residential probability."""
        street_lower = street.lower()

        # PO Box check
        if "po box" in street_lower or "p.o. box" in street_lower:
            return AddressType.PO_BOX, 0.3

        # CMRA check
        if is_cmra:
            return AddressType.CMRA, 0.2

        # TODO: Implement actual address database lookup
        # For now, return residential with medium confidence
        return AddressType.RESIDENTIAL, 0.7

    def _get_dwelling_type(self, street: str) -> Optional[str]:
        """Determine dwelling type from address."""
        street_lower = street.lower()

        if any(x in street_lower for x in ["apt", "apartment", "unit", "#"]):
            return "apartment"
        if "suite" in street_lower or "ste" in street_lower:
            return "commercial"
        if "floor" in street_lower or "fl " in street_lower:
            return "commercial"

        # Default assumption for standard addresses
        return "single_family"

    def get_risk_score(self, result: ResidentialScore) -> float:
        """Calculate risk score from residential scoring."""
        score = 0.0

        # CMRA is high risk for credit applications
        if result.is_cmra:
            score += 0.5

        # High-risk locations
        if result.is_high_risk_location:
            score += 0.4

        # PO Box is moderate risk
        if result.address_type == AddressType.PO_BOX:
            score += 0.3

        # Low residential probability
        score += (1.0 - result.residential_probability) * 0.3

        return min(1.0, score)
