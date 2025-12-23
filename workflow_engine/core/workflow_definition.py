"""Workflow definition model for core execution."""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from workflow_engine.dsl.schema import WorkflowDefinition as DSLWorkflowDefinition


class WorkflowDefinitionModel:
    """Core workflow definition model."""

    def __init__(
        self,
        id: UUID,
        name: str,
        version: str,
        dsl_definition: DSLWorkflowDefinition,
        description: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """Initialize workflow definition model."""
        self.id = id
        self.name = name
        self.version = version
        self.description = description
        self.dsl_definition = dsl_definition
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def get_task_by_id(self, task_id: str) -> Optional[Any]:
        """Get task by ID."""
        for task in self.dsl_definition.tasks:
            if task.id == task_id:
                return task
        return None

    def get_tasks_without_dependencies(self) -> list:
        """Get tasks that have no dependencies."""
        all_task_ids = {task.id for task in self.dsl_definition.tasks}
        tasks_without_deps = []
        for task in self.dsl_definition.tasks:
            if not task.depends_on or all(dep not in all_task_ids for dep in task.depends_on):
                tasks_without_deps.append(task)
        return tasks_without_deps

    def get_ready_tasks(self, completed_task_ids: set) -> list:
        """Get tasks that are ready to execute (all dependencies completed)."""
        ready = []
        for task in self.dsl_definition.tasks:
            if task.id in completed_task_ids:
                continue
            if not task.depends_on or all(dep in completed_task_ids for dep in task.depends_on):
                ready.append(task)
        return ready

