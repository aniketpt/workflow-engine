"""SQLAlchemy implementation of execution repository."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from workflow_engine.storage.models import WorkflowExecution, WorkflowExecutionStatus
from workflow_engine.storage.repositories.execution_repository import ExecutionRepository


class SQLAlchemyExecutionRepository(ExecutionRepository):
    """SQLAlchemy implementation of ExecutionRepository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Create a new workflow execution."""
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def get_by_id(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def get_by_temporal_id(self, temporal_workflow_id: str) -> Optional[WorkflowExecution]:
        """Get execution by Temporal workflow ID."""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.temporal_workflow_id == temporal_workflow_id)
        )
        return result.scalar_one_or_none()

    async def list_by_workflow(
        self,
        workflow_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowExecution]:
        """List executions for a workflow."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_definition_id == workflow_id)
            .offset(skip)
            .limit(limit)
            .order_by(WorkflowExecution.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[WorkflowExecutionStatus] = None,
    ) -> List[WorkflowExecution]:
        """List all executions with optional status filter."""
        query = select(WorkflowExecution)
        if status:
            query = query.where(WorkflowExecution.status == status)
        result = await self.session.execute(
            query.offset(skip).limit(limit).order_by(WorkflowExecution.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Update execution."""
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def update_status(
        self,
        execution_id: UUID,
        status: WorkflowExecutionStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[WorkflowExecution]:
        """Update execution status."""
        execution = await self.get_by_id(execution_id)
        if not execution:
            return None

        execution.status = status
        if result is not None:
            execution.result = result
        if error is not None:
            execution.error = error

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

