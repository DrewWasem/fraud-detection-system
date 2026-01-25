"""Authorized user abuse detection."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AUAccount:
    """Authorized user account details."""

    account_id: str
    primary_holder_ssn_hash: str
    added_date: datetime
    credit_limit: float
    account_age_months: int
    primary_holder_relationship: Optional[str]


@dataclass
class AUAbuseAnalysis:
    """Authorized user abuse analysis result."""

    identity_id: str
    ssn_hash: str
    au_account_count: int
    unrelated_au_count: int
    au_accounts: list[AUAccount]
    abuse_probability: float
    abuse_indicators: list[str]
    risk_level: str


class AuthorizedUserDetector:
    """Detects authorized user tradeline abuse patterns."""

    # Thresholds for abuse detection
    MAX_LEGITIMATE_AU_ACCOUNTS = 3
    MIN_SUSPICIOUS_AU_COUNT = 4
    HIGH_RISK_AU_COUNT = 6

    def __init__(self, bureau_connector=None, graph_client=None):
        """
        Initialize detector.

        Args:
            bureau_connector: Credit bureau data connector
            graph_client: Identity graph client
        """
        self._bureau = bureau_connector
        self._graph = graph_client

    def analyze(
        self,
        identity_id: str,
        ssn_hash: str,
    ) -> AUAbuseAnalysis:
        """
        Analyze authorized user patterns for an identity.

        Args:
            identity_id: Identity to analyze
            ssn_hash: Hashed SSN

        Returns:
            AUAbuseAnalysis with findings
        """
        # Get AU accounts
        au_accounts = self._get_au_accounts(ssn_hash)
        au_count = len(au_accounts)

        # Analyze relationships
        unrelated_count = self._count_unrelated_au(au_accounts, identity_id)

        # Identify abuse indicators
        indicators = self._identify_abuse_indicators(
            au_accounts, au_count, unrelated_count
        )

        # Calculate abuse probability
        abuse_prob = self._calculate_abuse_probability(
            au_count, unrelated_count, indicators
        )

        # Determine risk level
        risk_level = self._determine_risk_level(abuse_prob, indicators)

        return AUAbuseAnalysis(
            identity_id=identity_id,
            ssn_hash=ssn_hash,
            au_account_count=au_count,
            unrelated_au_count=unrelated_count,
            au_accounts=au_accounts,
            abuse_probability=abuse_prob,
            abuse_indicators=indicators,
            risk_level=risk_level,
        )

    def _get_au_accounts(self, ssn_hash: str) -> list[AUAccount]:
        """Get authorized user accounts for SSN."""
        if not self._bureau:
            return []

        # TODO: Implement actual bureau query
        tradelines = self._bureau.get_tradelines(ssn_hash)
        au_accounts = []

        for tradeline in tradelines:
            if tradeline.is_authorized_user:
                au_accounts.append(
                    AUAccount(
                        account_id=tradeline.tradeline_id,
                        primary_holder_ssn_hash="",  # Would need lookup
                        added_date=tradeline.opened_date,
                        credit_limit=tradeline.credit_limit,
                        account_age_months=0,  # Would calculate
                        primary_holder_relationship=None,
                    )
                )

        return au_accounts

    def _count_unrelated_au(
        self, au_accounts: list[AUAccount], identity_id: str
    ) -> int:
        """Count AU accounts where primary holder is not related."""
        if not self._graph:
            return 0

        unrelated = 0
        for au in au_accounts:
            # Check if primary holder is connected in identity graph
            # Legitimate AU typically involves family members
            relationship = self._check_relationship(
                identity_id, au.primary_holder_ssn_hash
            )
            if relationship is None:
                unrelated += 1

        return unrelated

    def _check_relationship(
        self, identity_id: str, other_ssn_hash: str
    ) -> Optional[str]:
        """Check relationship between identity and another SSN holder."""
        if not self._graph:
            return None

        # TODO: Query graph for relationship
        # Look for:
        # - Shared address (family)
        # - Same last name
        # - Known family relationship
        return None

    def _identify_abuse_indicators(
        self,
        au_accounts: list[AUAccount],
        au_count: int,
        unrelated_count: int,
    ) -> list[str]:
        """Identify specific abuse indicators."""
        indicators = []

        # Too many AU accounts
        if au_count >= self.HIGH_RISK_AU_COUNT:
            indicators.append("EXCESSIVE_AU_ACCOUNTS")
        elif au_count >= self.MIN_SUSPICIOUS_AU_COUNT:
            indicators.append("HIGH_AU_COUNT")

        # Most AU accounts are unrelated
        if au_count > 0 and unrelated_count / au_count > 0.7:
            indicators.append("MOSTLY_UNRELATED_AU")

        # All AU accounts (no primary accounts)
        # This would need additional data about primary accounts
        if au_count > 0:
            # Check if any recent additions
            recent_additions = sum(
                1
                for au in au_accounts
                if (datetime.now() - au.added_date).days < 180
            )
            if recent_additions >= 3:
                indicators.append("RAPID_AU_ADDITIONS")

        # High credit limit AU accounts
        high_limit_au = sum(1 for au in au_accounts if au.credit_limit > 10000)
        if high_limit_au >= 2:
            indicators.append("HIGH_LIMIT_AU_ACCOUNTS")

        # Very new accounts being AU'd on
        very_new_au = sum(
            1 for au in au_accounts if au.account_age_months < 6
        )
        if very_new_au >= 2:
            indicators.append("AU_ON_NEW_ACCOUNTS")

        return indicators

    def _calculate_abuse_probability(
        self,
        au_count: int,
        unrelated_count: int,
        indicators: list[str],
    ) -> float:
        """Calculate probability of AU abuse."""
        probability = 0.0

        # Base probability from count
        if au_count >= self.HIGH_RISK_AU_COUNT:
            probability += 0.4
        elif au_count >= self.MIN_SUSPICIOUS_AU_COUNT:
            probability += 0.25
        elif au_count >= self.MAX_LEGITIMATE_AU_ACCOUNTS:
            probability += 0.1

        # Unrelated accounts
        if au_count > 0:
            unrelated_ratio = unrelated_count / au_count
            probability += unrelated_ratio * 0.3

        # Indicator-based additions
        indicator_weights = {
            "EXCESSIVE_AU_ACCOUNTS": 0.2,
            "MOSTLY_UNRELATED_AU": 0.25,
            "RAPID_AU_ADDITIONS": 0.15,
            "HIGH_LIMIT_AU_ACCOUNTS": 0.1,
            "AU_ON_NEW_ACCOUNTS": 0.1,
        }

        for indicator in indicators:
            probability += indicator_weights.get(indicator, 0.05)

        return min(1.0, probability)

    def _determine_risk_level(
        self, abuse_prob: float, indicators: list[str]
    ) -> str:
        """Determine risk level from analysis."""
        if abuse_prob >= 0.8 or "EXCESSIVE_AU_ACCOUNTS" in indicators:
            return "critical"
        elif abuse_prob >= 0.6:
            return "high"
        elif abuse_prob >= 0.4:
            return "medium"
        elif abuse_prob >= 0.2:
            return "low"
        else:
            return "minimal"

    def find_au_rings(self) -> list[dict]:
        """
        Find rings of identities sharing AU relationships.

        AU fraud rings often involve:
        - Multiple synthetic identities being added as AU
        - Same primary accounts adding many AU users
        - Coordinated AU additions across accounts

        Returns:
            List of detected rings with member details
        """
        if not self._graph:
            return []

        # TODO: Implement graph-based ring detection
        # Query for patterns like:
        # - Same primary holder -> multiple AU identities
        # - AU identities sharing other PII elements
        return []
