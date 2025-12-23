"""Temporal workflow implementations."""

import asyncio
from typing import Dict, Any, List
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from workflow_engine.dsl.schema import WorkflowDefinition as DSLWorkflowDefinition, Task
from workflow_engine.core.task_executor import parse_duration, activity_registry


@workflow.defn
class WorkflowEngineWorkflow:
    """Main workflow engine workflow."""

    def __init__(self):
        """Initialize workflow."""
        self.task_results: Dict[str, Any] = {}
        self.failed_tasks: Dict[str, str] = {}

    @workflow.run
    async def run(self, workflow_data: tuple) -> Dict[str, Any]:
        """Execute workflow.

        Args:
            workflow_data: Tuple of (workflow_def, parameters)

        Returns:
            Final workflow result
        """
        # Unpack the tuple
        workflow_def_raw, parameters = workflow_data
        
        # Temporal serializes Pydantic models to dicts, so we need to deserialize back
        if isinstance(workflow_def_raw, dict):
            workflow_def = DSLWorkflowDefinition.model_validate(workflow_def_raw)
        else:
            # Already a Pydantic model
            workflow_def = workflow_def_raw
        
        completed_task_ids: set = set()
        all_task_ids = {task.id for task in workflow_def.tasks}

        # Execute tasks in dependency order
        while len(completed_task_ids) < len(all_task_ids):
            # Get ready tasks (all dependencies completed)
            ready_tasks = self._get_ready_tasks(workflow_def.tasks, completed_task_ids)

            if not ready_tasks:
                # Check if we have failed tasks that prevent progress
                remaining = all_task_ids - completed_task_ids
                if remaining:
                    failed_remaining = [tid for tid in remaining if tid in self.failed_tasks]
                    if failed_remaining:
                        raise Exception(f"Workflow failed: tasks {failed_remaining} failed and cannot proceed")
                break

            # Execute ready tasks (can be parallel)
            if len(ready_tasks) == 1:
                # Sequential execution
                task = ready_tasks[0]
                result = await self._execute_task_with_retry(task, workflow_def, parameters)
                self.task_results[task.id] = result
                completed_task_ids.add(task.id)
            else:
                # Parallel execution
                tasks_to_run = ready_tasks
                results = await asyncio.gather(
                    *[self._execute_task_with_retry(task, workflow_def, parameters) for task in tasks_to_run],
                    return_exceptions=True,
                )

                for task, result in zip(tasks_to_run, results):
                    if isinstance(result, Exception):
                        self.failed_tasks[task.id] = str(result)
                        raise Exception(f"Task '{task.id}' failed: {result}") from result
                    self.task_results[task.id] = result
                    completed_task_ids.add(task.id)

        # Return final result
        return {
            "status": "completed",
            "task_results": self.task_results,
        }

    async def _execute_task_with_retry(
        self,
        task: Task,
        workflow_def: DSLWorkflowDefinition,
        parameters: Dict[str, Any],
    ) -> Any:
        """Execute a task with retry logic.

        Args:
            task: Task to execute
            workflow_def: Workflow definition
            parameters: Workflow parameters

        Returns:
            Task result
        """
        # Prepare activity arguments
        # Only pass task.config to activities, not workflow parameters
        # Workflow parameters are for workflow-level logic, not activity execution
        activity_args = task.config.copy() if task.config else {}
        
        # Add task_id for activities that need it (e.g., human_approval)
        activity_args["task_id"] = task.id
        
        # Add workflow_execution_id for activities that need it (e.g., human_approval)
        # Extract execution ID from Temporal workflow ID (format: "workflow-{execution.id}")
        workflow_info = workflow.info()
        if workflow_info.workflow_id and workflow_info.workflow_id.startswith("workflow-"):
            execution_id_str = workflow_info.workflow_id.replace("workflow-", "")
            activity_args["workflow_execution_id"] = execution_id_str

        # Set timeout
        timeout = timedelta(hours=1)  # Default
        if task.timeout:
            timeout = parse_duration(task.timeout)

        # Get retry policy
        retry_policy = None
        if task.retry:
            dsl_retry = task.retry
            retry_policy = RetryPolicy(
                initial_interval=parse_duration(dsl_retry.initial_interval),
                backoff_coefficient=dsl_retry.multiplier,
                maximum_interval=parse_duration(dsl_retry.max_interval),
                maximum_attempts=dsl_retry.max_attempts,
            )

        # Execute activity based on activity_type using registry
        # Try to get activity function from registry, fallback to string name
        if activity_registry.has(task.activity_type):
            activity_func = activity_registry.get(task.activity_type)
            # Pass activity_args as a single dict argument (Temporal doesn't accept arbitrary kwargs)
            result = await workflow.execute_activity(
                activity_func,
                activity_args,  # Pass as single positional argument (dict)
                start_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )
        else:
            # Fallback to string name - Temporal will resolve it
            # Pass activity_args as a single dict argument (Temporal doesn't accept arbitrary kwargs)
            result = await workflow.execute_activity(
                task.activity_type,
                activity_args,  # Pass as single positional argument (dict)
                start_to_close_timeout=timeout,
                retry_policy=retry_policy,
            )

        return result

    @staticmethod
    def _get_ready_tasks(tasks: List[Task], completed_task_ids: set) -> List[Task]:
        """Get tasks ready to execute (all dependencies completed).

        Args:
            tasks: All tasks in workflow
            completed_task_ids: Set of completed task IDs

        Returns:
            List of ready tasks
        """
        ready = []
        for task in tasks:
            if task.id in completed_task_ids:
                continue
            if not task.depends_on or all(dep in completed_task_ids for dep in task.depends_on):
                ready.append(task)
        return ready

