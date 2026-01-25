"""Address normalization and standardization."""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NormalizedAddress:
    """Standardized address representation."""

    street_number: Optional[str]
    street_name: str
    street_type: Optional[str]
    unit_type: Optional[str]
    unit_number: Optional[str]
    city: str
    state: str
    zip_code: str
    zip_plus4: Optional[str]
    normalized_hash: str  # For deduplication
    original: str


class AddressNormalizer:
    """Normalizes addresses for consistent comparison."""

    # Street type mappings
    STREET_TYPES = {
        "street": "ST",
        "str": "ST",
        "st": "ST",
        "avenue": "AVE",
        "ave": "AVE",
        "av": "AVE",
        "boulevard": "BLVD",
        "blvd": "BLVD",
        "drive": "DR",
        "dr": "DR",
        "lane": "LN",
        "ln": "LN",
        "road": "RD",
        "rd": "RD",
        "court": "CT",
        "ct": "CT",
        "circle": "CIR",
        "cir": "CIR",
        "place": "PL",
        "pl": "PL",
        "way": "WAY",
        "highway": "HWY",
        "hwy": "HWY",
        "parkway": "PKWY",
        "pkwy": "PKWY",
    }

    # Unit type mappings
    UNIT_TYPES = {
        "apartment": "APT",
        "apt": "APT",
        "#": "APT",
        "unit": "UNIT",
        "suite": "STE",
        "ste": "STE",
        "floor": "FL",
        "fl": "FL",
        "building": "BLDG",
        "bldg": "BLDG",
    }

    # State abbreviations
    STATE_ABBREVS = {
        "alabama": "AL",
        "alaska": "AK",
        "arizona": "AZ",
        "arkansas": "AR",
        "california": "CA",
        "colorado": "CO",
        "connecticut": "CT",
        "delaware": "DE",
        "florida": "FL",
        "georgia": "GA",
        "hawaii": "HI",
        "idaho": "ID",
        "illinois": "IL",
        "indiana": "IN",
        "iowa": "IA",
        "kansas": "KS",
        "kentucky": "KY",
        "louisiana": "LA",
        "maine": "ME",
        "maryland": "MD",
        "massachusetts": "MA",
        "michigan": "MI",
        "minnesota": "MN",
        "mississippi": "MS",
        "missouri": "MO",
        "montana": "MT",
        "nebraska": "NE",
        "nevada": "NV",
        "new hampshire": "NH",
        "new jersey": "NJ",
        "new mexico": "NM",
        "new york": "NY",
        "north carolina": "NC",
        "north dakota": "ND",
        "ohio": "OH",
        "oklahoma": "OK",
        "oregon": "OR",
        "pennsylvania": "PA",
        "rhode island": "RI",
        "south carolina": "SC",
        "south dakota": "SD",
        "tennessee": "TN",
        "texas": "TX",
        "utah": "UT",
        "vermont": "VT",
        "virginia": "VA",
        "washington": "WA",
        "west virginia": "WV",
        "wisconsin": "WI",
        "wyoming": "WY",
    }

    def normalize(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
    ) -> NormalizedAddress:
        """Normalize an address to standard form."""
        original = f"{street}, {city}, {state} {zip_code}"

        # Normalize state
        state_norm = self._normalize_state(state)

        # Normalize ZIP
        zip_norm, zip_plus4 = self._normalize_zip(zip_code)

        # Normalize city
        city_norm = self._normalize_city(city)

        # Parse and normalize street
        street_parts = self._parse_street(street)

        # Generate hash for deduplication
        norm_hash = self._generate_hash(
            street_parts, city_norm, state_norm, zip_norm
        )

        return NormalizedAddress(
            street_number=street_parts.get("number"),
            street_name=street_parts.get("name", ""),
            street_type=street_parts.get("type"),
            unit_type=street_parts.get("unit_type"),
            unit_number=street_parts.get("unit_number"),
            city=city_norm,
            state=state_norm,
            zip_code=zip_norm,
            zip_plus4=zip_plus4,
            normalized_hash=norm_hash,
            original=original,
        )

    def _normalize_state(self, state: str) -> str:
        """Normalize state to 2-letter abbreviation."""
        state_lower = state.strip().lower()
        if state_lower in self.STATE_ABBREVS:
            return self.STATE_ABBREVS[state_lower]
        # Already abbreviated
        if len(state.strip()) == 2:
            return state.strip().upper()
        return state.strip().upper()

    def _normalize_zip(self, zip_code: str) -> tuple[str, Optional[str]]:
        """Normalize ZIP code, extract plus-4 if present."""
        zip_clean = re.sub(r"[^0-9]", "", zip_code)

        if len(zip_clean) >= 9:
            return zip_clean[:5], zip_clean[5:9]
        elif len(zip_clean) >= 5:
            return zip_clean[:5], None
        return zip_clean, None

    def _normalize_city(self, city: str) -> str:
        """Normalize city name."""
        city_clean = city.strip().upper()
        # Remove common abbreviations
        city_clean = re.sub(r"\bST\b", "SAINT", city_clean)
        city_clean = re.sub(r"\bMT\b", "MOUNT", city_clean)
        city_clean = re.sub(r"\bFT\b", "FORT", city_clean)
        return city_clean

    def _parse_street(self, street: str) -> dict:
        """Parse street address into components."""
        result = {}
        street_upper = street.strip().upper()

        # Extract street number
        number_match = re.match(r"^(\d+[-\d]*)\s+", street_upper)
        if number_match:
            result["number"] = number_match.group(1)
            street_upper = street_upper[number_match.end() :]

        # Extract unit
        unit_patterns = [
            r"\s+(APT|APARTMENT|UNIT|STE|SUITE|#)\s*([A-Z0-9-]+)$",
            r"\s+([A-Z0-9-]+)\s*$",  # Trailing unit number
        ]
        for pattern in unit_patterns:
            unit_match = re.search(pattern, street_upper)
            if unit_match:
                if len(unit_match.groups()) == 2:
                    unit_type = unit_match.group(1)
                    result["unit_type"] = self.UNIT_TYPES.get(
                        unit_type.lower(), unit_type
                    )
                    result["unit_number"] = unit_match.group(2)
                street_upper = street_upper[: unit_match.start()]
                break

        # Extract street type
        for long_form, abbrev in self.STREET_TYPES.items():
            pattern = rf"\b{long_form.upper()}\b\.?$"
            if re.search(pattern, street_upper):
                result["type"] = abbrev
                street_upper = re.sub(pattern, "", street_upper).strip()
                break

        result["name"] = street_upper.strip()
        return result

    def _generate_hash(
        self, street_parts: dict, city: str, state: str, zip_code: str
    ) -> str:
        """Generate normalized hash for address comparison."""
        import hashlib

        components = [
            street_parts.get("number", ""),
            street_parts.get("name", ""),
            street_parts.get("type", ""),
            street_parts.get("unit_type", ""),
            street_parts.get("unit_number", ""),
            city,
            state,
            zip_code,
        ]
        normalized = "|".join(c.upper() for c in components if c)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
