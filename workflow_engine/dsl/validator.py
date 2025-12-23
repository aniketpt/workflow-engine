"""Workflow definition validator."""

from typing import List, Dict, Any
from workflow_engine.dsl.schema import WorkflowDefinition, Task


class WorkflowValidator:
    """Validator for workflow definitions."""

    @staticmethod
    def validate(workflow: WorkflowDefinition) -> List[str]:
        """Validate workflow definition.

        Args:
            workflow: WorkflowDefinition to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[str] = []

        # Validate name
        if not workflow.name or not workflow.name.strip():
            errors.append("Workflow name is required")

        # Validate version
        if not workflow.version:
            errors.append("Workflow version is required")

        # Validate tasks
        if not workflow.tasks:
            errors.append("Workflow must have at least one task")
            return errors

        # Validate task IDs are unique
        task_ids = [task.id for task in workflow.tasks]
        if len(task_ids) != len(set(task_ids)):
            errors.append("Task IDs must be unique")

        # Validate each task
        for task in workflow.tasks:
            task_errors = WorkflowValidator._validate_task(task, workflow.tasks)
            errors.extend([f"Task '{task.id}': {e}" for e in task_errors])

        # Validate parameters
        param_names = [p.name for p in workflow.parameters]
        if len(param_names) != len(set(param_names)):
            errors.append("Parameter names must be unique")

        return errors

    @staticmethod
    def _validate_task(task: Task, all_tasks: List[Task]) -> List[str]:
        """Validate a single task.

        Args:
            task: Task to validate
            all_tasks: All tasks in the workflow

        Returns:
            List of validation errors for this task
        """
        errors: List[str] = []

        # Validate task ID
        if not task.id or not task.id.strip():
            errors.append("Task ID is required")

        # Validate task name
        if not task.name or not task.name.strip():
            errors.append("Task name is required")

        # Validate activity type
        if task.type == "activity" and not task.activity_type:
            errors.append("Activity type is required for activity tasks")

        # Validate dependencies
        if task.depends_on:
            task_ids = {t.id for t in all_tasks}
            for dep_id in task.depends_on:
                if dep_id not in task_ids:
                    errors.append(f"Dependency '{dep_id}' does not exist")
                if dep_id == task.id:
                    errors.append("Task cannot depend on itself")

        return errors

    @staticmethod
    def is_valid(workflow: WorkflowDefinition) -> bool:
        """Check if workflow is valid.

        Args:
            workflow: WorkflowDefinition to check

        Returns:
            True if valid, False otherwise
        """
        return len(WorkflowValidator.validate(workflow)) == 0

