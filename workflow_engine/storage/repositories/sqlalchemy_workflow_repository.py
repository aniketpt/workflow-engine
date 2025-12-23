"""SQLAlchemy implementation of workflow repository."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from workflow_engine.storage.models import WorkflowDefinition
from workflow_engine.storage.repositories.workflow_repository import WorkflowRepository


class SQLAlchemyWorkflowRepository(WorkflowRepository):
    """SQLAlchemy implementation of WorkflowRepository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Create a new workflow definition."""
        self.session.add(workflow)
        await self.session.flush()
        await self.session.refresh(workflow)
        return workflow

    async def get_by_id(self, workflow_id: UUID) -> Optional[WorkflowDefinition]:
        """Get workflow definition by ID."""
        result = await self.session.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[WorkflowDefinition]:
        """Get workflow definition by name."""
        result = await self.session.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[WorkflowDefinition]:
        """List all workflow definitions."""
        result = await self.session.execute(
            select(WorkflowDefinition).offset(skip).limit(limit).order_by(WorkflowDefinition.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Update workflow definition."""
        await self.session.flush()
        await self.session.refresh(workflow)
        return workflow

    async def delete(self, workflow_id: UUID) -> bool:
        """Delete workflow definition."""
        workflow = await self.get_by_id(workflow_id)
        if workflow:
            await self.session.delete(workflow)
            await self.session.flush()
            return True
        return False

