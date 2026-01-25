"""Email pattern analysis for synthetic identity detection."""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailPattern:
    """Email pattern analysis result."""

    email: str
    local_part: str
    domain: str
    has_numbers: bool
    number_suffix: Optional[str]
    has_random_string: bool
    matches_name: bool
    pattern_type: str
    synthetic_score: float


class EmailPatternDetector:
    """Detects suspicious email patterns indicative of synthetic identities."""

    # Random-looking patterns
    RANDOM_PATTERNS = [
        r"^[a-z]{8,}[0-9]{3,}$",  # Letters followed by many numbers
        r"^[a-z0-9]{15,}$",  # Long alphanumeric without structure
        r"^[a-z]{2,3}[0-9]{5,}$",  # Short prefix with many numbers
        r"^[a-z]+_[a-z]+_[0-9]+$",  # Systematic naming pattern
    ]

    # Synthetic-looking patterns
    SYNTHETIC_PATTERNS = [
        r"^(user|account|test|temp|fake)[0-9]+$",
        r"^[a-z]+\.[a-z]+[0-9]{4,}$",  # name.name1234...
        r"^[a-z]{2}[0-9]{6,}$",  # Two letters + many numbers
    ]

    def __init__(self):
        self._random_regex = [re.compile(p) for p in self.RANDOM_PATTERNS]
        self._synthetic_regex = [re.compile(p) for p in self.SYNTHETIC_PATTERNS]

    def analyze(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> EmailPattern:
        """
        Analyze email for synthetic patterns.

        Args:
            email: Email address
            first_name: Claimed first name
            last_name: Claimed last name

        Returns:
            EmailPattern with analysis
        """
        if "@" not in email:
            return self._invalid_result(email)

        local_part, domain = email.lower().split("@", 1)

        # Check for numbers
        has_numbers = bool(re.search(r"\d", local_part))
        number_suffix = self._extract_number_suffix(local_part)

        # Check for random strings
        has_random = self._check_random_pattern(local_part)

        # Check if matches claimed name
        matches_name = self._check_name_match(local_part, first_name, last_name)

        # Determine pattern type
        pattern_type = self._determine_pattern_type(
            local_part, has_numbers, has_random, matches_name
        )

        # Calculate synthetic score
        synthetic_score = self._calculate_synthetic_score(
            local_part, has_numbers, has_random, matches_name, number_suffix
        )

        return EmailPattern(
            email=email,
            local_part=local_part,
            domain=domain,
            has_numbers=has_numbers,
            number_suffix=number_suffix,
            has_random_string=has_random,
            matches_name=matches_name,
            pattern_type=pattern_type,
            synthetic_score=synthetic_score,
        )

    def _invalid_result(self, email: str) -> EmailPattern:
        """Return result for invalid email."""
        return EmailPattern(
            email=email,
            local_part="",
            domain="",
            has_numbers=False,
            number_suffix=None,
            has_random_string=False,
            matches_name=False,
            pattern_type="invalid",
            synthetic_score=1.0,
        )

    def _extract_number_suffix(self, local_part: str) -> Optional[str]:
        """Extract trailing numbers from local part."""
        match = re.search(r"(\d+)$", local_part)
        return match.group(1) if match else None

    def _check_random_pattern(self, local_part: str) -> bool:
        """Check if local part looks randomly generated."""
        for regex in self._random_regex:
            if regex.match(local_part):
                return True

        # Check entropy/randomness heuristics
        if len(local_part) > 12:
            # Check for lack of vowels (likely random)
            vowel_ratio = sum(1 for c in local_part if c in "aeiou") / len(local_part)
            if vowel_ratio < 0.15:
                return True

        return False

    def _check_name_match(
        self,
        local_part: str,
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> bool:
        """Check if email local part matches claimed name."""
        if not first_name and not last_name:
            return False

        # Clean local part
        clean_local = re.sub(r"[0-9._-]", "", local_part.lower())

        first_lower = first_name.lower() if first_name else ""
        last_lower = last_name.lower() if last_name else ""

        # Check various patterns
        patterns_to_check = []
        if first_name:
            patterns_to_check.append(first_lower)
            patterns_to_check.append(first_lower[0] if first_lower else "")
        if last_name:
            patterns_to_check.append(last_lower)
        if first_name and last_name:
            patterns_to_check.append(f"{first_lower}{last_lower}")
            patterns_to_check.append(f"{last_lower}{first_lower}")
            patterns_to_check.append(f"{first_lower[0]}{last_lower}")
            patterns_to_check.append(f"{first_lower}{last_lower[0]}")

        for pattern in patterns_to_check:
            if pattern and pattern in clean_local:
                return True

        return False

    def _determine_pattern_type(
        self,
        local_part: str,
        has_numbers: bool,
        has_random: bool,
        matches_name: bool,
    ) -> str:
        """Determine the type of email pattern."""
        if has_random:
            return "random_generated"

        for regex in self._synthetic_regex:
            if regex.match(local_part):
                return "synthetic_pattern"

        if matches_name and not has_numbers:
            return "name_based"

        if matches_name and has_numbers:
            return "name_with_numbers"

        if has_numbers:
            return "numbered"

        return "standard"

    def _calculate_synthetic_score(
        self,
        local_part: str,
        has_numbers: bool,
        has_random: bool,
        matches_name: bool,
        number_suffix: Optional[str],
    ) -> float:
        """Calculate likelihood of synthetic identity."""
        score = 0.0

        # Random patterns are highly suspicious
        if has_random:
            score += 0.5

        # Synthetic patterns
        for regex in self._synthetic_regex:
            if regex.match(local_part):
                score += 0.4
                break

        # Numbers in email are slightly suspicious
        if has_numbers:
            score += 0.1
            # Long number suffixes more suspicious
            if number_suffix and len(number_suffix) >= 4:
                score += 0.2

        # Not matching name is somewhat suspicious
        if not matches_name:
            score += 0.15

        return min(1.0, score)
