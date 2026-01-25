"""Investigation case management."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CaseStatus(Enum):
    """Case status values."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    SAR_FILED = "sar_filed"
    CLOSED_CONFIRMED = "closed_confirmed"
    CLOSED_FALSE_POSITIVE = "closed_false_positive"


class CasePriority(Enum):
    """Case priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CaseNote:
    """Note attached to a case."""
    note_id: str
    author: str
    content: str
    created_at: datetime


@dataclass
class Case:
    """Investigation case."""
    case_id: str
    identity_id: str
    status: CaseStatus
    priority: CasePriority
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: datetime
    synthetic_score: float
    risk_level: str
    triggered_signals: list[str]
    notes: list[CaseNote] = field(default_factory=list)
    related_cases: list[str] = field(default_factory=list)
    sar_reference: Optional[str] = None


class CaseManager:
    """Manages investigation cases."""

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._cases: dict[str, Case] = {}

    def create_case(
        self,
        identity_id: str,
        synthetic_score: float,
        risk_level: str,
        triggered_signals: list[str],
        priority: Optional[CasePriority] = None,
    ) -> Case:
        """Create a new investigation case."""
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now()

        # Auto-determine priority if not specified
        if priority is None:
            if risk_level == "critical":
                priority = CasePriority.CRITICAL
            elif risk_level == "high":
                priority = CasePriority.HIGH
            elif risk_level == "medium":
                priority = CasePriority.MEDIUM
            else:
                priority = CasePriority.LOW

        case = Case(
            case_id=case_id,
            identity_id=identity_id,
            status=CaseStatus.OPEN,
            priority=priority,
            assigned_to=None,
            created_at=now,
            updated_at=now,
            synthetic_score=synthetic_score,
            risk_level=risk_level,
            triggered_signals=triggered_signals,
        )

        self._cases[case_id] = case
        logger.info(f"Created case {case_id} for identity {identity_id[:8]}")
        return case

    def get_case(self, case_id: str) -> Optional[Case]:
        """Get a case by ID."""
        return self._cases.get(case_id)

    def update_status(self, case_id: str, status: CaseStatus) -> bool:
        """Update case status."""
        case = self._cases.get(case_id)
        if not case:
            return False
        case.status = status
        case.updated_at = datetime.now()
        return True

    def assign_case(self, case_id: str, analyst: str) -> bool:
        """Assign case to analyst."""
        case = self._cases.get(case_id)
        if not case:
            return False
        case.assigned_to = analyst
        case.status = CaseStatus.IN_PROGRESS
        case.updated_at = datetime.now()
        return True

    def add_note(self, case_id: str, author: str, content: str) -> bool:
        """Add note to case."""
        case = self._cases.get(case_id)
        if not case:
            return False
        note = CaseNote(
            note_id=uuid.uuid4().hex[:8],
            author=author,
            content=content,
            created_at=datetime.now(),
        )
        case.notes.append(note)
        case.updated_at = datetime.now()
        return True

    def link_cases(self, case_id_1: str, case_id_2: str) -> bool:
        """Link related cases."""
        case1 = self._cases.get(case_id_1)
        case2 = self._cases.get(case_id_2)
        if not case1 or not case2:
            return False
        if case_id_2 not in case1.related_cases:
            case1.related_cases.append(case_id_2)
        if case_id_1 not in case2.related_cases:
            case2.related_cases.append(case_id_1)
        return True

    def list_cases(
        self,
        status: Optional[CaseStatus] = None,
        priority: Optional[CasePriority] = None,
        assigned_to: Optional[str] = None,
    ) -> list[Case]:
        """List cases with optional filters."""
        cases = list(self._cases.values())
        if status:
            cases = [c for c in cases if c.status == status]
        if priority:
            cases = [c for c in cases if c.priority == priority]
        if assigned_to:
            cases = [c for c in cases if c.assigned_to == assigned_to]
        return sorted(cases, key=lambda c: c.created_at, reverse=True)

    def get_cases_for_identity(self, identity_id: str) -> list[Case]:
        """Get all cases for an identity."""
        return [c for c in self._cases.values() if c.identity_id == identity_id]
