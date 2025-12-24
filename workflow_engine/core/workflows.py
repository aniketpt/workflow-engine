"""Temporal workflow implementations."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from workflow_engine.dsl.schema import WorkflowDefinition as DSLWorkflowDefinition, Task
from workflow_engine.core.task_executor import parse_duration, activity_registry

logger = logging.getLogger(__name__)


@workflow.defn
class WorkflowEngineWorkflow:
    """Main workflow engine workflow."""

    def __init__(self):
        """Initialize workflow."""
        self.task_results: Dict[str, Any] = {}
        self.failed_tasks: Dict[str, str] = {}
        self.completed_tasks_order: List[str] = []  # Track completion order for compensation
        self.task_definitions: Dict[str, Task] = {}  # Store task definitions for compensation

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
        
        # Store task definitions for compensation access
        for task in workflow_def.tasks:
            self.task_definitions[task.id] = task
        
        completed_task_ids: set = set()
        all_task_ids = {task.id for task in workflow_def.tasks}

        # Extract execution ID from Temporal workflow ID for status updates
        workflow_info = workflow.info()
        execution_id_str = None
        if workflow_info.workflow_id and workflow_info.workflow_id.startswith("workflow-"):
            execution_id_str = workflow_info.workflow_id.replace("workflow-", "")
        
        # Execute tasks in dependency order with compensation support
        workflow_result = None
        workflow_error = None
        workflow_status = "COMPLETED"
        
        try:
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
                    self.completed_tasks_order.append(task.id)
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
                        self.completed_tasks_order.append(task.id)

            # Workflow completed successfully
            workflow_result = {
                "status": "completed",
                "task_results": self.task_results,
            }
            return workflow_result
            
        except Exception as e:
            # Workflow failed - execute compensations in reverse order
            workflow_status = "FAILED"
            workflow_error = str(e)
            await self._run_compensations(workflow_def, parameters)
            # Re-raise the exception so Temporal marks workflow as failed
            raise
        finally:
            # Update database status regardless of success or failure
            if execution_id_str:
                try:
                    await self._update_execution_status(
                        execution_id_str,
                        workflow_status,
                        workflow_result,
                        workflow_error,
                    )
                except Exception as e:
                    # Log but don't fail workflow if status update fails
                    logger.error(f"Failed to update execution status: {e}")

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
        # Copy task.config and substitute template variables {{ parameter_name }} with workflow parameters
        activity_args = self._substitute_templates(task.config.copy() if task.config else {}, parameters) if task.config else {}
        
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

        # Use activity_id for better UI visibility
        activity_id = f"task_{task.id}"

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
                activity_id=activity_id,
            )
        else:
            # Fallback to string name - Temporal will resolve it
            # Pass activity_args as a single dict argument (Temporal doesn't accept arbitrary kwargs)
            result = await workflow.execute_activity(
                task.activity_type,
                activity_args,  # Pass as single positional argument (dict)
                start_to_close_timeout=timeout,
                retry_policy=retry_policy,
                activity_id=activity_id,
            )

        return result

    async def _execute_compensation(
        self,
        task: Task,
        workflow_def: DSLWorkflowDefinition,
        parameters: Dict[str, Any],
    ) -> None:
        """Execute compensation activity for a task.

        Args:
            task: Task that needs compensation
            workflow_def: Workflow definition
            parameters: Workflow parameters
        """
        if not task.compensation:
            return  # No compensation defined for this task

        compensation = task.compensation

        # Prepare compensation activity arguments
        # Compensation config can access task results via template syntax
        # For now, we pass task_results in the args so activities can access them
        compensation_args = compensation.config.copy() if compensation.config else {}
        compensation_args["task_id"] = task.id
        compensation_args["original_task_id"] = task.id
        compensation_args["task_results"] = self.task_results
        compensation_args["workflow_parameters"] = parameters

        # Add workflow_execution_id for activities that need it
        try:
            workflow_info = workflow.info()
            if workflow_info.workflow_id and workflow_info.workflow_id.startswith("workflow-"):
                execution_id_str = workflow_info.workflow_id.replace("workflow-", "")
                compensation_args["workflow_execution_id"] = execution_id_str
        except Exception:
            # Not in workflow context (e.g., during tests), skip
            pass

        # Set timeout
        timeout = timedelta(hours=1)  # Default
        if compensation.timeout:
            timeout = parse_duration(compensation.timeout)

        # Get retry policy for compensation
        retry_policy = None
        if compensation.retry:
            dsl_retry = compensation.retry
            retry_policy = RetryPolicy(
                initial_interval=parse_duration(dsl_retry.initial_interval),
                backoff_coefficient=dsl_retry.multiplier,
                maximum_interval=parse_duration(dsl_retry.max_interval),
                maximum_attempts=dsl_retry.max_attempts,
            )

        # Use activity_id for better UI visibility
        activity_id = f"compensate_{task.id}"

        # Execute compensation activity
        try:
            if activity_registry.has(compensation.activity_type):
                activity_func = activity_registry.get(compensation.activity_type)
                await workflow.execute_activity(
                    activity_func,
                    compensation_args,
                    start_to_close_timeout=timeout,
                    retry_policy=retry_policy,
                    activity_id=activity_id,
                )
            else:
                # Fallback to string name
                await workflow.execute_activity(
                    compensation.activity_type,
                    compensation_args,
                    start_to_close_timeout=timeout,
                    retry_policy=retry_policy,
                    activity_id=activity_id,
                )
        except Exception as e:
            # Log compensation failure but continue with other compensations
            # This ensures we attempt all compensations even if one fails
            logger.error(f"Compensation for task '{task.id}' failed: {e}")
            # Re-raise to surface the error, but we'll catch it in _run_compensations
            raise

    async def _run_compensations(
        self,
        workflow_def: DSLWorkflowDefinition,
        parameters: Dict[str, Any],
    ) -> None:
        """Execute compensations for all completed tasks in reverse order.

        Args:
            workflow_def: Workflow definition
            parameters: Workflow parameters
        """
        if not self.completed_tasks_order:
            return  # No completed tasks to compensate

        # Execute compensations in reverse order of completion
        for task_id in reversed(self.completed_tasks_order):
            task = self.task_definitions.get(task_id)
            if not task:
                continue  # Task definition not found, skip

            if task.compensation:
                try:
                    await self._execute_compensation(task, workflow_def, parameters)
                except Exception as e:
                    # Log but continue with other compensations
                    logger.error(
                        f"Failed to execute compensation for task '{task_id}': {e}. "
                        "Continuing with other compensations."
                    )

    async def _update_execution_status(
        self,
        execution_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update workflow execution status in database.

        Args:
            execution_id: Execution ID (UUID string)
            status: Status string ("COMPLETED", "FAILED", etc.)
            result: Optional workflow result
            error: Optional error message
        """
        if not activity_registry.has("update_execution_status"):
            return  # Activity not registered, skip update
        
        update_activity = activity_registry.get("update_execution_status")
        update_args = {
            "execution_id": execution_id,
            "status": status,
            "result": result,
            "error": error,
        }
        
        try:
            await workflow.execute_activity(
                update_activity,
                update_args,
                start_to_close_timeout=timedelta(seconds=30),
                activity_id=f"update_status_{execution_id}",
            )
        except Exception as e:
            # Log but don't fail - status update is best effort
            logger.error(f"Failed to update execution status via activity: {e}")

    @staticmethod
    def _substitute_templates(config: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively substitute {{ parameter_name }} templates in config with parameter values.
        
        Args:
            config: Configuration dictionary (may contain nested dicts/lists)
            parameters: Workflow parameters dictionary
            
        Returns:
            Config with templates substituted
        """
        import re
        
        if isinstance(config, dict):
            result = {}
            for key, value in config.items():
                result[key] = WorkflowEngineWorkflow._substitute_templates(value, parameters)
            return result
        elif isinstance(config, list):
            return [WorkflowEngineWorkflow._substitute_templates(item, parameters) for item in config]
        elif isinstance(config, str):
            # Replace {{ parameter_name }} with parameter value
            def replace_template(match):
                param_name = match.group(1).strip()
                param_value = parameters.get(param_name, match.group(0))
                # Preserve type for non-strings, convert to string for template replacement
                if isinstance(param_value, (bool, int, float)):
                    return str(param_value).lower() if isinstance(param_value, bool) else str(param_value)
                return str(param_value)
            
            pattern = r'\{\{\s*([^}]+)\s*\}\}'
            return re.sub(pattern, replace_template, config)
        else:
            return config

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

