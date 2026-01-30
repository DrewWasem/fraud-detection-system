"""Credit bureau data connector."""

import hashlib
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Bureau(Enum):
    """Credit bureau identifiers."""

    EXPERIAN = "experian"
    EQUIFAX = "equifax"
    TRANSUNION = "transunion"


@dataclass
class CreditFileSnapshot:
    """Point-in-time snapshot of credit file."""

    ssn_hash: str
    bureau: Bureau
    snapshot_date: datetime
    file_creation_date: Optional[datetime]
    num_tradelines: int
    oldest_tradeline_date: Optional[datetime]
    total_credit_limit: float
    total_balance: float
    num_inquiries_6mo: int
    num_new_accounts_6mo: int
    credit_score: Optional[int]
    has_bankruptcy: bool
    has_collections: bool
    authorized_user_accounts: int


@dataclass
class TradeLine:
    """Individual credit tradeline."""

    tradeline_id: str
    account_type: str
    opened_date: datetime
    credit_limit: float
    current_balance: float
    payment_status: str
    is_authorized_user: bool
    creditor_name: str


class BureauConnectorBase(ABC):
    """Abstract base class for bureau connectors."""

    @abstractmethod
    def get_credit_file(self, ssn_hash: str) -> Optional[CreditFileSnapshot]:
        """Retrieve credit file snapshot."""
        pass

    @abstractmethod
    def get_tradelines(self, ssn_hash: str) -> list[TradeLine]:
        """Retrieve tradelines for identity."""
        pass


class BureauConnector(BureauConnectorBase):
    """Multi-bureau credit data connector."""

    def __init__(self, bureau: Bureau, api_key: Optional[str] = None):
        self.bureau = bureau
        self.api_key = api_key
        self._connected = False

    def connect(self) -> None:
        """Establish connection to bureau API."""
        # TODO: Implement actual bureau API connection
        logger.info(f"Connecting to {self.bureau.value} bureau...")
        self._connected = True

    def get_credit_file(self, ssn_hash: str) -> Optional[CreditFileSnapshot]:
        """Retrieve credit file snapshot for given SSN hash."""
        if not self._connected:
            raise RuntimeError("Not connected to bureau. Call connect() first.")

        logger.debug(f"Fetching credit file for {ssn_hash[:8]}...")
        # TODO: Implement actual bureau API call
        return None

    def get_tradelines(self, ssn_hash: str) -> list[TradeLine]:
        """Retrieve all tradelines for given SSN hash."""
        if not self._connected:
            raise RuntimeError("Not connected to bureau. Call connect() first.")

        logger.debug(f"Fetching tradelines for {ssn_hash[:8]}...")
        # TODO: Implement actual bureau API call
        return []

    def get_credit_file_age(self, ssn_hash: str) -> Optional[int]:
        """Get age of credit file in months."""
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file or not credit_file.file_creation_date:
            return None

        age_days = (datetime.now() - credit_file.file_creation_date).days
        return age_days // 30

    def get_authorized_user_count(self, ssn_hash: str) -> int:
        """Count authorized user accounts."""
        tradelines = self.get_tradelines(ssn_hash)
        return sum(1 for t in tradelines if t.is_authorized_user)

    def is_thin_file(self, ssn_hash: str, min_tradelines: int = 3) -> bool:
        """Check if credit file is considered thin."""
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file:
            return True
        return credit_file.num_tradelines < min_tradelines


class MockBureauConnector(BureauConnectorBase):
    """
    Mock bureau connector for testing and development.

    Generates realistic test data based on SSN hash to ensure
    deterministic results for the same input.
    """

    # Creditor names for generating tradelines
    CREDITORS = [
        "Bank of America",
        "Chase",
        "Wells Fargo",
        "Citi",
        "Capital One",
        "Discover",
        "American Express",
        "US Bank",
        "PNC Bank",
        "TD Bank",
        "Synchrony",
        "Barclays",
    ]

    ACCOUNT_TYPES = [
        "credit_card",
        "auto_loan",
        "mortgage",
        "personal_loan",
        "student_loan",
        "retail_card",
    ]

    def __init__(self, bureau: Bureau = Bureau.EXPERIAN):
        self.bureau = bureau
        self._connected = True

    def connect(self) -> None:
        """Mock connection - always succeeds."""
        self._connected = True

    def _get_deterministic_seed(self, ssn_hash: str) -> int:
        """Get a deterministic seed from SSN hash for reproducible results."""
        # Use first 8 chars of hash to generate seed
        hash_int = int(hashlib.md5(ssn_hash.encode()).hexdigest()[:8], 16)
        return hash_int

    def _is_synthetic_profile(self, ssn_hash: str) -> bool:
        """
        Determine if this SSN hash represents a synthetic identity.

        Uses the hash to deterministically assign ~15% as synthetic.
        """
        seed = self._get_deterministic_seed(ssn_hash)
        return (seed % 100) < 15  # 15% synthetic rate

    def get_credit_file(self, ssn_hash: str) -> Optional[CreditFileSnapshot]:
        """
        Generate mock credit file based on SSN hash.

        Synthetic identities get thin files with recent creation dates.
        Legitimate identities get established files.
        """
        seed = self._get_deterministic_seed(ssn_hash)
        rng = random.Random(seed)

        now = datetime.now()
        is_synthetic = self._is_synthetic_profile(ssn_hash)

        if is_synthetic:
            # Synthetic identity profile: thin file, recent, suspicious patterns
            file_age_months = rng.randint(3, 24)
            num_tradelines = rng.randint(1, 4)
            au_accounts = rng.randint(1, 3)  # More AU accounts
            credit_score = rng.randint(620, 720)  # Decent but not great
            num_inquiries = rng.randint(3, 8)  # Many inquiries
            num_new_accounts = rng.randint(2, 5)  # Rapid account opening

            # Thin files often have no oldest tradeline or recent one
            oldest_tradeline_months = min(file_age_months, rng.randint(3, 18))

            total_limit = rng.randint(5000, 25000)
            total_balance = int(total_limit * rng.uniform(0.6, 0.9))  # High utilization

        else:
            # Legitimate identity profile: established file
            file_age_months = rng.randint(36, 240)  # 3-20 years
            num_tradelines = rng.randint(5, 15)
            au_accounts = rng.randint(0, 1)  # Few AU accounts
            credit_score = rng.randint(680, 820)
            num_inquiries = rng.randint(0, 3)
            num_new_accounts = rng.randint(0, 2)

            oldest_tradeline_months = rng.randint(
                int(file_age_months * 0.7), file_age_months
            )

            total_limit = rng.randint(20000, 150000)
            total_balance = int(total_limit * rng.uniform(0.1, 0.4))  # Low utilization

        file_creation_date = now - timedelta(days=file_age_months * 30)
        oldest_tradeline_date = now - timedelta(days=oldest_tradeline_months * 30)

        # Some files have bankruptcy or collections
        has_bankruptcy = rng.random() < 0.03  # 3%
        has_collections = rng.random() < 0.08  # 8%

        return CreditFileSnapshot(
            ssn_hash=ssn_hash,
            bureau=self.bureau,
            snapshot_date=now,
            file_creation_date=file_creation_date,
            num_tradelines=num_tradelines,
            oldest_tradeline_date=oldest_tradeline_date,
            total_credit_limit=total_limit,
            total_balance=total_balance,
            num_inquiries_6mo=num_inquiries,
            num_new_accounts_6mo=num_new_accounts,
            credit_score=credit_score,
            has_bankruptcy=has_bankruptcy,
            has_collections=has_collections,
            authorized_user_accounts=au_accounts,
        )

    def get_tradelines(self, ssn_hash: str) -> list[TradeLine]:
        """Generate mock tradelines based on SSN hash."""
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file:
            return []

        seed = self._get_deterministic_seed(ssn_hash)
        rng = random.Random(seed + 1)  # Different seed for tradelines

        now = datetime.now()
        is_synthetic = self._is_synthetic_profile(ssn_hash)
        tradelines = []

        num_tradelines = credit_file.num_tradelines
        au_count = credit_file.authorized_user_accounts

        for i in range(num_tradelines):
            # Determine if this is an AU account
            is_au = i < au_count

            if is_au:
                # AU accounts are typically older credit cards
                account_type = "credit_card"
                opened_months_ago = rng.randint(24, 120)
                credit_limit = rng.randint(10000, 50000)
                balance = int(credit_limit * rng.uniform(0.1, 0.3))
                payment_status = "current"
            elif is_synthetic:
                # Synthetic identity tradelines
                account_type = rng.choice(["credit_card", "retail_card", "personal_loan"])
                opened_months_ago = rng.randint(1, 18)
                credit_limit = rng.randint(1000, 10000)
                balance = int(credit_limit * rng.uniform(0.5, 0.95))
                payment_status = rng.choice(["current", "current", "30_days_late"])
            else:
                # Legitimate tradelines
                account_type = rng.choice(self.ACCOUNT_TYPES)
                file_age_months = (now - credit_file.file_creation_date).days // 30
                opened_months_ago = rng.randint(6, max(7, file_age_months))

                if account_type == "mortgage":
                    credit_limit = rng.randint(100000, 500000)
                elif account_type == "auto_loan":
                    credit_limit = rng.randint(15000, 50000)
                else:
                    credit_limit = rng.randint(2000, 30000)

                balance = int(credit_limit * rng.uniform(0.05, 0.4))
                payment_status = rng.choices(
                    ["current", "30_days_late"],
                    weights=[0.95, 0.05],
                )[0]

            creditor = rng.choice(self.CREDITORS)
            opened_date = now - timedelta(days=opened_months_ago * 30)
            tradeline_id = f"TL-{ssn_hash[:4]}-{i:03d}"

            tradelines.append(
                TradeLine(
                    tradeline_id=tradeline_id,
                    account_type=account_type,
                    opened_date=opened_date,
                    credit_limit=credit_limit,
                    current_balance=balance,
                    payment_status=payment_status,
                    is_authorized_user=is_au,
                    creditor_name=creditor,
                )
            )

        return tradelines

    def get_credit_file_age(self, ssn_hash: str) -> Optional[int]:
        """Get age of credit file in months."""
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file or not credit_file.file_creation_date:
            return None

        age_days = (datetime.now() - credit_file.file_creation_date).days
        return age_days // 30

    def get_authorized_user_count(self, ssn_hash: str) -> int:
        """Count authorized user accounts."""
        tradelines = self.get_tradelines(ssn_hash)
        return sum(1 for t in tradelines if t.is_authorized_user)

    def is_thin_file(self, ssn_hash: str, min_tradelines: int = 3) -> bool:
        """Check if credit file is considered thin."""
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file:
            return True
        return credit_file.num_tradelines < min_tradelines

    def get_credit_utilization(self, ssn_hash: str) -> float:
        """Calculate credit utilization ratio."""
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file or credit_file.total_credit_limit == 0:
            return 0.0
        return credit_file.total_balance / credit_file.total_credit_limit

    def get_file_age_vs_oldest_tradeline(self, ssn_hash: str) -> Optional[int]:
        """
        Get difference between file age and oldest tradeline in months.

        Large differences can indicate synthetic identity buildup.
        """
        credit_file = self.get_credit_file(ssn_hash)
        if not credit_file:
            return None

        if not credit_file.file_creation_date or not credit_file.oldest_tradeline_date:
            return None

        file_age = credit_file.file_creation_date
        oldest = credit_file.oldest_tradeline_date

        diff_days = (oldest - file_age).days
        return diff_days // 30

    def analyze_for_synthetic_signals(self, ssn_hash: str) -> dict:
        """
        Analyze credit file for synthetic identity signals.

        Returns dict with various risk indicators.
        """
        credit_file = self.get_credit_file(ssn_hash)
        tradelines = self.get_tradelines(ssn_hash)

        if not credit_file:
            return {
                "has_data": False,
                "signals": ["NO_CREDIT_FILE"],
                "risk_score": 0.5,
            }

        signals = []
        risk_score = 0.0

        # Check for thin file
        if credit_file.num_tradelines < 3:
            signals.append("THIN_FILE")
            risk_score += 0.15

        # Check file age
        if credit_file.file_creation_date:
            file_age_months = (datetime.now() - credit_file.file_creation_date).days // 30
            if file_age_months < 24:
                signals.append("YOUNG_CREDIT_FILE")
                risk_score += 0.2

        # Check AU abuse
        au_ratio = credit_file.authorized_user_accounts / max(1, credit_file.num_tradelines)
        if au_ratio > 0.5:
            signals.append("HIGH_AU_RATIO")
            risk_score += 0.25

        # Check inquiry velocity
        if credit_file.num_inquiries_6mo > 5:
            signals.append("HIGH_INQUIRY_VELOCITY")
            risk_score += 0.15

        # Check new account velocity
        if credit_file.num_new_accounts_6mo > 3:
            signals.append("RAPID_ACCOUNT_OPENING")
            risk_score += 0.2

        # Check utilization
        utilization = self.get_credit_utilization(ssn_hash)
        if utilization > 0.8:
            signals.append("HIGH_UTILIZATION")
            risk_score += 0.1

        # Check for late payments on new accounts
        recent_late = sum(
            1
            for t in tradelines
            if t.payment_status != "current"
            and (datetime.now() - t.opened_date).days < 365
        )
        if recent_late > 0:
            signals.append("RECENT_DELINQUENCY")
            risk_score += 0.1

        return {
            "has_data": True,
            "signals": signals,
            "risk_score": min(1.0, risk_score),
            "file_age_months": (datetime.now() - credit_file.file_creation_date).days // 30
            if credit_file.file_creation_date
            else None,
            "num_tradelines": credit_file.num_tradelines,
            "au_accounts": credit_file.authorized_user_accounts,
            "utilization": utilization,
            "credit_score": credit_file.credit_score,
        }
