"""Approval repository interface."""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from workflow_engine.storage.models import ApprovalRequest, ApprovalStatus


class ApprovalRepository(ABC):
    """Repository interface for approval requests."""

    @abstractmethod
    async def create(self, approval: ApprovalRequest) -> ApprovalRequest:
        """Create a new approval request."""
        pass

    @abstractmethod
    async def get_by_approval_id(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by approval_id."""
        pass

    @abstractmethod
    async def get_by_id(self, approval_request_id: UUID) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        pass

    @abstractmethod
    async def update(self, approval: ApprovalRequest) -> ApprovalRequest:
        """Update approval request."""
        pass

    @abstractmethod
    async def list_pending(self, skip: int = 0, limit: int = 100) -> List[ApprovalRequest]:
        """List pending approval requests."""
        pass

    @abstractmethod
    async def list_by_execution_id(
        self, execution_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ApprovalRequest]:
        """List approval requests for a workflow execution."""
        pass

