"""Repository for workflow definitions."""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from workflow_engine.storage.models import WorkflowDefinition


class WorkflowRepository(ABC):
    """Abstract repository for workflow definitions."""

    @abstractmethod
    async def create(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Create a new workflow definition."""
        pass

    @abstractmethod
    async def get_by_id(self, workflow_id: UUID) -> Optional[WorkflowDefinition]:
        """Get workflow definition by ID."""
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[WorkflowDefinition]:
        """Get workflow definition by name."""
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[WorkflowDefinition]:
        """List all workflow definitions."""
        pass

    @abstractmethod
    async def update(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Update workflow definition."""
        pass

    @abstractmethod
    async def delete(self, workflow_id: UUID) -> bool:
        """Delete workflow definition."""
        pass

