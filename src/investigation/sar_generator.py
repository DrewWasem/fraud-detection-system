"""SAR (Suspicious Activity Report) generation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SARReport:
    """Suspicious Activity Report."""
    sar_id: str
    case_id: str
    identity_id: str
    generated_at: datetime
    narrative: str
    suspicious_activity_type: str
    amount_involved: Optional[float]
    date_range_start: datetime
    date_range_end: datetime
    filing_institution: str
    status: str


class SARGenerator:
    """Generates Suspicious Activity Reports for synthetic identity fraud."""

    def __init__(self, institution_info: dict = None):
        self._institution = institution_info or {
            "name": "Financial Institution",
            "id": "FI-001",
        }

    def generate(
        self,
        case_id: str,
        identity_id: str,
        detection_result: dict,
        account_info: Optional[dict] = None,
    ) -> SARReport:
        """Generate SAR for synthetic identity case."""
        import uuid

        sar_id = f"SAR-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now()

        # Generate narrative
        narrative = self._generate_narrative(
            identity_id, detection_result, account_info
        )

        # Determine activity type
        activity_type = self._determine_activity_type(detection_result)

        # Calculate amount involved
        amount = self._calculate_amount(account_info)

        return SARReport(
            sar_id=sar_id,
            case_id=case_id,
            identity_id=identity_id,
            generated_at=now,
            narrative=narrative,
            suspicious_activity_type=activity_type,
            amount_involved=amount,
            date_range_start=now,  # Would be actual date range
            date_range_end=now,
            filing_institution=self._institution["name"],
            status="draft",
        )

    def _generate_narrative(
        self,
        identity_id: str,
        detection_result: dict,
        account_info: Optional[dict],
    ) -> str:
        """Generate SAR narrative."""
        parts = []

        # Opening
        parts.append(
            f"This SAR is being filed to report suspected synthetic identity fraud "
            f"involving identity {identity_id[:8]}."
        )

        # Detection summary
        score = detection_result.get("synthetic_score", 0)
        signals = detection_result.get("triggered_signals", [])

        parts.append(
            f"The identity received a synthetic fraud score of {score:.0%}."
        )

        if signals:
            parts.append(f"Key indicators: {', '.join(signals[:5])}.")

        # Account activity if available
        if account_info:
            if account_info.get("bust_out_risk"):
                parts.append(
                    f"Bust-out risk assessment indicates elevated risk of "
                    f"imminent default."
                )

        # Closing
        parts.append(
            "Investigation is ongoing and additional information may be "
            "provided in a supplemental filing."
        )

        return " ".join(parts)

    def _determine_activity_type(self, detection_result: dict) -> str:
        """Determine suspicious activity type code."""
        signals = detection_result.get("triggered_signals", [])

        if "BUST_OUT" in signals or detection_result.get("bust_out_risk", 0) > 0.7:
            return "SYNTHETIC_IDENTITY_BUST_OUT"
        elif "SHARED_SSN" in signals:
            return "SYNTHETIC_IDENTITY_RING"
        else:
            return "SYNTHETIC_IDENTITY_FRAUD"

    def _calculate_amount(self, account_info: Optional[dict]) -> Optional[float]:
        """Calculate total amount involved."""
        if not account_info:
            return None

        total = 0.0
        total += account_info.get("current_balance", 0)
        total += account_info.get("credit_limit", 0)
        return total if total > 0 else None

    def submit(self, sar: SARReport) -> bool:
        """Submit SAR to FinCEN."""
        # TODO: Implement actual FinCEN submission
        # This would use the BSA E-Filing System
        sar.status = "submitted"
        return True
