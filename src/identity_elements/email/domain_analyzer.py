"""Email domain reputation and analysis."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DomainType(Enum):
    """Types of email domains."""

    MAJOR_PROVIDER = "major_provider"  # Gmail, Yahoo, Outlook
    CORPORATE = "corporate"
    EDUCATIONAL = "educational"
    GOVERNMENT = "government"
    DISPOSABLE = "disposable"
    FREE_UNCOMMON = "free_uncommon"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


@dataclass
class DomainAnalysis:
    """Domain analysis result."""

    domain: str
    domain_type: DomainType
    reputation_score: float  # 0-1, higher is better
    is_disposable: bool
    is_free: bool
    domain_age_days: Optional[int]
    has_mx_records: bool
    is_catchall: bool
    risk_score: float


class DomainAnalyzer:
    """Analyzes email domains for fraud risk."""

    # Major email providers (legitimate, low risk)
    MAJOR_PROVIDERS = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "protonmail.com",
        "mail.com",
    }

    # Known disposable email domains (partial list)
    DISPOSABLE_DOMAINS = {
        "tempmail.com",
        "guerrillamail.com",
        "10minutemail.com",
        "mailinator.com",
        "throwaway.email",
        "temp-mail.org",
        "fakemailgenerator.com",
        "getnada.com",
        "maildrop.cc",
        "yopmail.com",
        "sharklasers.com",
        "guerrillamail.info",
        "grr.la",
        "spam4.me",
        "trash-mail.com",
    }

    # Less common free providers (moderate risk)
    FREE_UNCOMMON = {
        "zoho.com",
        "gmx.com",
        "yandex.com",
        "tutanota.com",
        "fastmail.com",
        "hushmail.com",
        "inbox.com",
        "mail.ru",
    }

    def __init__(self, disposable_list_path: Optional[str] = None):
        """
        Initialize domain analyzer.

        Args:
            disposable_list_path: Path to extended disposable domain list
        """
        self._disposable_domains = self.DISPOSABLE_DOMAINS.copy()
        if disposable_list_path:
            self._load_disposable_list(disposable_list_path)

    def _load_disposable_list(self, path: str) -> None:
        """Load extended disposable domain list."""
        try:
            with open(path, "r") as f:
                for line in f:
                    domain = line.strip().lower()
                    if domain:
                        self._disposable_domains.add(domain)
            logger.info(f"Loaded {len(self._disposable_domains)} disposable domains")
        except Exception as e:
            logger.error(f"Failed to load disposable list: {e}")

    def analyze(self, email: str) -> DomainAnalysis:
        """
        Analyze email domain.

        Args:
            email: Email address to analyze

        Returns:
            DomainAnalysis with findings
        """
        # Extract domain
        if "@" not in email:
            return self._invalid_email_result(email)

        domain = email.split("@")[1].lower()

        # Check domain type
        domain_type = self._get_domain_type(domain)

        # Check if disposable
        is_disposable = domain in self._disposable_domains

        # Check if free
        is_free = domain in self.MAJOR_PROVIDERS or domain in self.FREE_UNCOMMON

        # Calculate reputation and risk
        reputation = self._calculate_reputation(domain, domain_type, is_disposable)
        risk_score = self._calculate_risk(domain_type, is_disposable)

        return DomainAnalysis(
            domain=domain,
            domain_type=domain_type,
            reputation_score=reputation,
            is_disposable=is_disposable,
            is_free=is_free,
            domain_age_days=None,  # TODO: Implement domain age lookup
            has_mx_records=True,  # TODO: Implement MX check
            is_catchall=False,  # TODO: Implement catchall detection
            risk_score=risk_score,
        )

    def _invalid_email_result(self, email: str) -> DomainAnalysis:
        """Return result for invalid email."""
        return DomainAnalysis(
            domain="",
            domain_type=DomainType.UNKNOWN,
            reputation_score=0.0,
            is_disposable=False,
            is_free=False,
            domain_age_days=None,
            has_mx_records=False,
            is_catchall=False,
            risk_score=1.0,
        )

    def _get_domain_type(self, domain: str) -> DomainType:
        """Determine domain type."""
        if domain in self.MAJOR_PROVIDERS:
            return DomainType.MAJOR_PROVIDER
        if domain in self._disposable_domains:
            return DomainType.DISPOSABLE
        if domain in self.FREE_UNCOMMON:
            return DomainType.FREE_UNCOMMON
        if domain.endswith(".edu"):
            return DomainType.EDUCATIONAL
        if domain.endswith(".gov"):
            return DomainType.GOVERNMENT
        return DomainType.CUSTOM

    def _calculate_reputation(
        self, domain: str, domain_type: DomainType, is_disposable: bool
    ) -> float:
        """Calculate domain reputation score."""
        if is_disposable:
            return 0.1
        if domain_type == DomainType.GOVERNMENT:
            return 0.95
        if domain_type == DomainType.EDUCATIONAL:
            return 0.9
        if domain_type == DomainType.MAJOR_PROVIDER:
            return 0.8
        if domain_type == DomainType.FREE_UNCOMMON:
            return 0.6
        if domain_type == DomainType.CUSTOM:
            return 0.7  # Could be legitimate business
        return 0.5

    def _calculate_risk(self, domain_type: DomainType, is_disposable: bool) -> float:
        """Calculate fraud risk score."""
        if is_disposable:
            return 0.9
        if domain_type == DomainType.DISPOSABLE:
            return 0.9
        if domain_type == DomainType.FREE_UNCOMMON:
            return 0.4
        if domain_type == DomainType.MAJOR_PROVIDER:
            return 0.2
        if domain_type == DomainType.GOVERNMENT:
            return 0.1
        if domain_type == DomainType.EDUCATIONAL:
            return 0.15
        return 0.3
