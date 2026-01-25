"""Investigation API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class CreateCaseRequest(BaseModel):
    """Request model for creating a case."""
    identity_id: str
    priority: Optional[str] = None
    notes: Optional[str] = None


class UpdateCaseRequest(BaseModel):
    """Request model for updating a case."""
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None


class AddNoteRequest(BaseModel):
    """Request model for adding a note."""
    author: str
    content: str


@router.get("/cases")
async def list_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = Query(default=50, le=100),
):
    """List investigation cases."""
    return {
        "cases": [],
        "total_count": 0,
    }


@router.post("/cases")
async def create_case(request: CreateCaseRequest):
    """Create a new investigation case."""
    return {
        "case_id": "CASE-NEW",
        "identity_id": request.identity_id,
        "status": "open",
    }


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get case details."""
    return {
        "case_id": case_id,
        "status": "unknown",
        "identity_id": "",
        "notes": [],
    }


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, request: UpdateCaseRequest):
    """Update a case."""
    return {"case_id": case_id, "updated": True}


@router.post("/cases/{case_id}/notes")
async def add_case_note(case_id: str, request: AddNoteRequest):
    """Add note to a case."""
    return {"case_id": case_id, "note_added": True}


@router.get("/cases/{case_id}/report")
async def get_case_report(case_id: str):
    """Get full investigation report for a case."""
    return {
        "case_id": case_id,
        "report": {},
    }


@router.post("/cases/{case_id}/sar")
async def generate_sar(case_id: str):
    """Generate SAR for a case."""
    return {
        "case_id": case_id,
        "sar_id": "SAR-NEW",
        "status": "draft",
    }
