"""SQLAlchemy implementation of approval repository."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from workflow_engine.storage.models import ApprovalRequest, ApprovalStatus
from workflow_engine.storage.repositories.approval_repository import ApprovalRepository


class SQLAlchemyApprovalRepository(ApprovalRepository):
    """SQLAlchemy implementation of ApprovalRepository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create(self, approval: ApprovalRequest) -> ApprovalRequest:
        """Create a new approval request."""
        self.session.add(approval)
        await self.session.flush()
        await self.session.refresh(approval)
        return approval

    async def get_by_approval_id(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by approval_id."""
        result = await self.session.execute(
            select(ApprovalRequest).where(ApprovalRequest.approval_id == approval_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, approval_request_id: UUID) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        result = await self.session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_request_id)
        )
        return result.scalar_one_or_none()

    async def update(self, approval: ApprovalRequest) -> ApprovalRequest:
        """Update approval request."""
        # Add the approval to the session if it's not already tracked
        self.session.add(approval)
        await self.session.flush()
        await self.session.refresh(approval)
        return approval

    async def list_pending(self, skip: int = 0, limit: int = 100) -> List[ApprovalRequest]:
        """List pending approval requests."""
        result = await self.session.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING)
            .offset(skip)
            .limit(limit)
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_execution_id(
        self, execution_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ApprovalRequest]:
        """List approval requests for a workflow execution."""
        result = await self.session.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.workflow_execution_id == execution_id)
            .offset(skip)
            .limit(limit)
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list(result.scalars().all())

