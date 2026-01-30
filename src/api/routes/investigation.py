"""Investigation API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.api import dependencies
from src.investigation.case_manager import CaseStatus, CasePriority

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateCaseRequest(BaseModel):
    """Request model for creating a case."""

    identity_id: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    synthetic_score: Optional[float] = None
    risk_level: Optional[str] = None
    signals: Optional[list[str]] = None


class UpdateCaseRequest(BaseModel):
    """Request model for updating a case."""

    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None


class AddNoteRequest(BaseModel):
    """Request model for adding a note."""

    author: str
    content: str


def _status_to_enum(status: str) -> Optional[CaseStatus]:
    """Convert status string to enum."""
    status_map = {
        "open": CaseStatus.OPEN,
        "in_progress": CaseStatus.IN_PROGRESS,
        "pending_review": CaseStatus.PENDING_REVIEW,
        "sar_filed": CaseStatus.SAR_FILED,
        "closed_confirmed": CaseStatus.CLOSED_CONFIRMED,
        "closed_false_positive": CaseStatus.CLOSED_FALSE_POSITIVE,
    }
    return status_map.get(status.lower())


def _priority_to_enum(priority: str) -> Optional[CasePriority]:
    """Convert priority string to enum."""
    priority_map = {
        "critical": CasePriority.CRITICAL,
        "high": CasePriority.HIGH,
        "medium": CasePriority.MEDIUM,
        "low": CasePriority.LOW,
    }
    return priority_map.get(priority.lower())


def _case_to_dict(case) -> dict:
    """Convert Case object to dict for API response."""
    return {
        "case_id": case.case_id,
        "identity_id": case.identity_id,
        "status": case.status.value,
        "priority": case.priority.value,
        "assigned_to": case.assigned_to,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "synthetic_score": case.synthetic_score,
        "risk_level": case.risk_level,
        "triggered_signals": case.triggered_signals,
        "notes": [
            {
                "note_id": n.note_id,
                "author": n.author,
                "content": n.content,
                "created_at": n.created_at.isoformat(),
            }
            for n in case.notes
        ],
        "related_cases": case.related_cases,
        "sar_reference": case.sar_reference,
    }


@router.get("/cases")
async def list_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = Query(default=50, le=100),
):
    """
    List investigation cases.

    Supports filtering by status, priority, and assignee.
    """
    try:
        case_manager = dependencies.get_case_manager()

        # Convert filters
        status_enum = _status_to_enum(status) if status else None
        priority_enum = _priority_to_enum(priority) if priority else None

        cases = case_manager.list_cases(
            status=status_enum,
            priority=priority_enum,
            assigned_to=assigned_to,
        )

        # Apply limit
        cases = cases[:limit]

        return {
            "cases": [_case_to_dict(c) for c in cases],
            "total_count": len(cases),
            "filters": {
                "status": status,
                "priority": priority,
                "assigned_to": assigned_to,
            },
        }

    except Exception as e:
        logger.error(f"Error listing cases: {e}")
        return {
            "cases": [],
            "total_count": 0,
            "error": str(e),
        }


@router.post("/cases")
async def create_case(request: CreateCaseRequest):
    """
    Create a new investigation case.

    Automatically creates a case for an identity that requires investigation.
    """
    try:
        case_manager = dependencies.get_case_manager()

        # Determine priority
        priority = None
        if request.priority:
            priority = _priority_to_enum(request.priority)

        # Create the case
        case = case_manager.create_case(
            identity_id=request.identity_id,
            synthetic_score=request.synthetic_score or 0.0,
            risk_level=request.risk_level or "medium",
            triggered_signals=request.signals or [],
            priority=priority,
        )

        # Add initial note if provided
        if request.notes:
            case_manager.add_note(case.case_id, "system", request.notes)

        return _case_to_dict(case)

    except Exception as e:
        logger.error(f"Error creating case: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create case: {str(e)}")


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get case details."""
    try:
        case_manager = dependencies.get_case_manager()
        case = case_manager.get_case(case_id)

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        return _case_to_dict(case)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting case: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get case: {str(e)}")


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, request: UpdateCaseRequest):
    """
    Update a case.

    Supports updating status, assignee, and priority.
    """
    try:
        case_manager = dependencies.get_case_manager()
        case = case_manager.get_case(case_id)

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Update status
        if request.status:
            status_enum = _status_to_enum(request.status)
            if status_enum:
                case_manager.update_status(case_id, status_enum)

        # Update assignee
        if request.assigned_to:
            case_manager.assign_case(case_id, request.assigned_to)

        # Update priority
        if request.priority:
            priority_enum = _priority_to_enum(request.priority)
            if priority_enum:
                case.priority = priority_enum

        # Get updated case
        updated_case = case_manager.get_case(case_id)
        return _case_to_dict(updated_case)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating case: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update case: {str(e)}")


@router.post("/cases/{case_id}/notes")
async def add_case_note(case_id: str, request: AddNoteRequest):
    """Add note to a case."""
    try:
        case_manager = dependencies.get_case_manager()
        case = case_manager.get_case(case_id)

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        success = case_manager.add_note(case_id, request.author, request.content)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to add note")

        # Return updated case
        updated_case = case_manager.get_case(case_id)
        return {
            "case_id": case_id,
            "note_added": True,
            "total_notes": len(updated_case.notes),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding note: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add note: {str(e)}")


@router.get("/cases/{case_id}/report")
async def get_case_report(case_id: str):
    """
    Get full investigation report for a case.

    Generates a comprehensive report including identity analysis,
    graph connections, and risk assessment.
    """
    try:
        case_manager = dependencies.get_case_manager()
        case = case_manager.get_case(case_id)

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Get identity graph information
        identity_graph = dependencies.get_identity_graph()
        shared_elements = {}
        graph_info = {}

        try:
            shared_elements = identity_graph.find_shared_elements(case.identity_id)
            graph_info = identity_graph.get_identity_graph(case.identity_id, depth=2)
        except Exception as e:
            logger.warning(f"Failed to get graph info for report: {e}")

        # Get graph features
        graph_features = {}
        try:
            graph_extractor = dependencies.get_graph_feature_extractor()
            features = graph_extractor.extract_features(case.identity_id)
            graph_features = {
                "degree": features.degree,
                "cluster_size": features.cluster_size,
                "shared_ssn_count": features.shared_ssn_count,
                "shared_address_count": features.shared_address_count,
                "shared_phone_count": features.shared_phone_count,
            }
        except Exception as e:
            logger.warning(f"Failed to get graph features for report: {e}")

        from datetime import datetime as dt
        return {
            "case_id": case_id,
            "report": {
                "case_details": _case_to_dict(case),
                "identity_analysis": {
                    "synthetic_score": case.synthetic_score,
                    "risk_level": case.risk_level,
                    "triggered_signals": case.triggered_signals,
                },
                "graph_analysis": {
                    "shared_elements": shared_elements,
                    "connected_nodes": len(graph_info.get("nodes", [])),
                    "features": graph_features,
                },
                "recommendations": _generate_recommendations(case),
            },
            "generated_at": dt.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )


def _generate_recommendations(case) -> list[str]:
    """Generate investigation recommendations based on case details."""
    recommendations = []

    if case.risk_level == "critical":
        recommendations.append("IMMEDIATE_REVIEW_REQUIRED")
        recommendations.append("CONSIDER_ACCOUNT_FREEZE")
        recommendations.append("PREPARE_SAR_FILING")

    if "SHARED_SSN" in case.triggered_signals:
        recommendations.append("INVESTIGATE_SSN_SHARING")
        recommendations.append("VERIFY_IDENTITY_DOCUMENTATION")

    if "HIGH_PHONE_VELOCITY" in case.triggered_signals:
        recommendations.append("INVESTIGATE_PHONE_PATTERNS")
        recommendations.append("CHECK_VOIP_STATUS")

    if case.synthetic_score > 0.7:
        recommendations.append("HIGH_SYNTHETIC_PROBABILITY")
        recommendations.append("ENHANCED_VERIFICATION_REQUIRED")

    if not recommendations:
        recommendations.append("STANDARD_REVIEW_PROCESS")

    return recommendations


@router.post("/cases/{case_id}/sar")
async def generate_sar(case_id: str):
    """
    Generate SAR for a case.

    Creates a draft Suspicious Activity Report based on case findings.
    """
    try:
        case_manager = dependencies.get_case_manager()
        case = case_manager.get_case(case_id)

        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Generate SAR ID
        import hashlib
        from datetime import datetime

        sar_id = f"SAR-{hashlib.sha256(f'{case_id}{datetime.now().isoformat()}'.encode()).hexdigest()[:8].upper()}"

        # Update case with SAR reference
        case.sar_reference = sar_id
        case_manager.update_status(case_id, CaseStatus.SAR_FILED)
        case_manager.add_note(case_id, "system", f"SAR generated: {sar_id}")

        return {
            "case_id": case_id,
            "sar_id": sar_id,
            "status": "draft",
            "generated_at": datetime.now().isoformat(),
            "next_steps": [
                "Review SAR draft",
                "Add supporting documentation",
                "Submit to FinCEN",
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating SAR: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate SAR: {str(e)}")


@router.post("/cases/{case_id}/link/{related_case_id}")
async def link_cases(case_id: str, related_case_id: str):
    """Link two related cases."""
    try:
        case_manager = dependencies.get_case_manager()

        # Verify both cases exist
        case1 = case_manager.get_case(case_id)
        case2 = case_manager.get_case(related_case_id)

        if not case1:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        if not case2:
            raise HTTPException(
                status_code=404, detail=f"Case {related_case_id} not found"
            )

        success = case_manager.link_cases(case_id, related_case_id)

        return {
            "case_id": case_id,
            "related_case_id": related_case_id,
            "linked": success,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking cases: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to link cases: {str(e)}")


@router.get("/cases/identity/{identity_id}")
async def get_cases_for_identity(identity_id: str):
    """Get all cases for an identity."""
    try:
        case_manager = dependencies.get_case_manager()
        cases = case_manager.get_cases_for_identity(identity_id)

        return {
            "identity_id": identity_id,
            "cases": [_case_to_dict(c) for c in cases],
            "total_count": len(cases),
        }

    except Exception as e:
        logger.error(f"Error getting cases for identity: {e}")
        return {
            "identity_id": identity_id,
            "cases": [],
            "total_count": 0,
            "error": str(e),
        }
