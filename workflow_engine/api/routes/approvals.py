"""Approval management routes."""

from typing import Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query

from workflow_engine.api.schemas import (
    ApprovalRequestResponse,
    ApprovalListResponse,
    ApprovalActionRequest,
)
from workflow_engine.storage.models import ApprovalStatus
from workflow_engine.storage.database import get_async_session
from workflow_engine.storage.repositories import SQLAlchemyApprovalRepository

router = APIRouter(prefix="/approvals", tags=["approvals"])


async def get_approval_repository():
    """Dependency to get approval repository."""
    async for session in get_async_session():
        yield SQLAlchemyApprovalRepository(session)
        break


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    status_filter: Optional[ApprovalStatus] = Query(None, alias="status", description="Filter by status"),
    execution_id: Optional[UUID] = Query(None, description="Filter by workflow execution ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    repo: SQLAlchemyApprovalRepository = Depends(get_approval_repository),
):
    """List approval requests with optional filters."""
    if status_filter == ApprovalStatus.PENDING and not execution_id:
        # Default to pending approvals if no specific filter
        approvals = await repo.list_pending(skip=skip, limit=limit)
    elif execution_id:
        approvals = await repo.list_by_execution_id(execution_id, skip=skip, limit=limit)
        if status_filter:
            approvals = [a for a in approvals if a.status == status_filter]
    else:
        # For now, just return pending if no filter
        approvals = await repo.list_pending(skip=skip, limit=limit)
    
    return ApprovalListResponse(
        approvals=[ApprovalRequestResponse.model_validate(a) for a in approvals],
        total=len(approvals),
    )


@router.get("/{approval_id}", response_model=ApprovalRequestResponse)
async def get_approval(
    approval_id: str,
    repo: SQLAlchemyApprovalRepository = Depends(get_approval_repository),
):
    """Get approval request by approval_id."""
    approval = await repo.get_by_approval_id(approval_id)
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return ApprovalRequestResponse.model_validate(approval)


@router.post("/{approval_id}/action", response_model=ApprovalRequestResponse)
async def approve_or_reject(
    approval_id: str,
    request: ApprovalActionRequest,
    repo: SQLAlchemyApprovalRepository = Depends(get_approval_repository),
):
    """Approve or reject an approval request."""
    approval = await repo.get_by_approval_id(approval_id)
    
    # If approval not found or already resolved, try to find a pending one with similar ID
    # This handles the case where the base approval_id was used but a new one was created with execution ID appended
    if not approval or approval.status != ApprovalStatus.PENDING:
        # Get all pending approvals and find one that starts with the requested approval_id
        pending_approvals = await repo.list_pending(skip=0, limit=100)
        matching_pending = None
        for pending in pending_approvals:
            if pending.approval_id.startswith(approval_id):
                matching_pending = pending
                break
        
        if matching_pending:
            approval = matching_pending
        elif not approval:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval request is already {approval.status.value}, cannot modify"
            )
    
    # Update approval status
    approval.status = ApprovalStatus.APPROVED if request.approved else ApprovalStatus.REJECTED
    approval.approved_by = request.approved_by
    approval.comment = request.comment
    approval.responded_at = datetime.utcnow()
    
    approval = await repo.update(approval)
    
    # Explicitly commit the session to ensure changes are persisted
    await repo.session.commit()
    
    return ApprovalRequestResponse.model_validate(approval)

