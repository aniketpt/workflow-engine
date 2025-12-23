"""Repository for workflow executions."""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from workflow_engine.storage.models import WorkflowExecution, WorkflowExecutionStatus


class ExecutionRepository(ABC):
    """Abstract repository for workflow executions."""

    @abstractmethod
    async def create(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Create a new workflow execution."""
        pass

    @abstractmethod
    async def get_by_id(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        pass

    @abstractmethod
    async def get_by_temporal_id(self, temporal_workflow_id: str) -> Optional[WorkflowExecution]:
        """Get execution by Temporal workflow ID."""
        pass

    @abstractmethod
    async def list_by_workflow(
        self,
        workflow_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowExecution]:
        """List executions for a workflow."""
        pass

    @abstractmethod
    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[WorkflowExecutionStatus] = None,
    ) -> List[WorkflowExecution]:
        """List all executions with optional status filter."""
        pass

    @abstractmethod
    async def update(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Update execution."""
        pass

    @abstractmethod
    async def update_status(
        self,
        execution_id: UUID,
        status: WorkflowExecutionStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[WorkflowExecution]:
        """Update execution status."""
        pass

