"""Credit bureau data connector."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
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
