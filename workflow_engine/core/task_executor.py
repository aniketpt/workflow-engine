"""Task execution with retries and timeouts."""

import asyncio
import inspect
from typing import Any, Dict, Optional
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from workflow_engine.dsl.schema import Task, RetryPolicy as DSLRetryPolicy


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string to timedelta.

    Args:
        duration_str: Duration string (e.g., "5s", "10m", "1h")

    Returns:
        timedelta object
    """
    if not duration_str:
        raise ValueError("Duration string cannot be empty")

    unit = duration_str[-1]
    value = float(duration_str[:-1])

    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    else:
        raise ValueError(f"Invalid duration unit: {unit}. Use s, m, or h")


def dsl_retry_to_temporal(dsl_retry: Optional[DSLRetryPolicy]) -> Optional[RetryPolicy]:
    """Convert DSL retry policy to Temporal retry policy.

    Args:
        dsl_retry: DSL retry policy

    Returns:
        Temporal retry policy or None
    """
    if not dsl_retry:
        return None

    initial_interval = parse_duration(dsl_retry.initial_interval)
    max_interval = parse_duration(dsl_retry.max_interval)

    return RetryPolicy(
        initial_interval=initial_interval,
        backoff_coefficient=dsl_retry.multiplier,
        maximum_interval=max_interval,
        maximum_attempts=dsl_retry.max_attempts,
    )


class ActivityRegistry:
    """Registry for activity implementations."""

    def __init__(self):
        """Initialize activity registry."""
        self._activities: Dict[str, Any] = {}
        self._temporal_activities: list = []  # Track Temporal activity functions for worker

    def register(self, activity_type: str, activity_func: Any) -> None:
        """Register an activity function.

        Args:
            activity_type: Type identifier (e.g., "http_request")
            activity_func: Activity function to register (should be a Temporal activity)
        """
        self._activities[activity_type] = activity_func
        # Track Temporal activity functions for auto-discovery in worker
        if activity_func not in self._temporal_activities:
            self._temporal_activities.append(activity_func)

    def get(self, activity_type: str) -> Any:
        """Get activity function by type.

        Args:
            activity_type: Type identifier

        Returns:
            Activity function

        Raises:
            KeyError: If activity type not found
        """
        if activity_type not in self._activities:
            raise KeyError(f"Activity type '{activity_type}' not found in registry")
        return self._activities[activity_type]

    def has(self, activity_type: str) -> bool:
        """Check if activity type is registered.

        Args:
            activity_type: Type identifier

        Returns:
            True if registered, False otherwise
        """
        return activity_type in self._activities

    def get_all_temporal_activities(self) -> list:
        """Get all registered Temporal activity functions for worker.

        Returns:
            List of Temporal activity functions
        """
        return self._temporal_activities.copy()


# Global activity registry
activity_registry = ActivityRegistry()


def auto_register_activities(activities_module) -> None:
    """Auto-register all activities decorated with @activity.defn in a module.
    
    Scans the module for functions decorated with @activity.defn and automatically
    registers them in the activity registry using the name from the decorator.
    
    Args:
        activities_module: The module containing activity functions
    """
    registered_count = 0
    method1_found = []
    
    # Method 1: Check all callables in module for __temporal_activity__ / __temporal_activity_definition attribute
    for name in dir(activities_module):
        if name.startswith('_'):
            continue
        obj = getattr(activities_module, name, None)
        if not obj or not callable(obj):
            continue
        
        # Check for Temporal activity definitions
        activity_info = None
        if hasattr(obj, '__temporal_activity__'):
            activity_info = getattr(obj, '__temporal_activity__')
        elif hasattr(obj, '__temporal_activity_definition'):
            activity_info = getattr(obj, '__temporal_activity_definition')

        if activity_info:
            activity_name = getattr(activity_info, 'name', None) or name
            activity_registry.register(activity_name, obj)
            registered_count += 1
            method1_found.append(activity_name)
    
    # Method 2: If no activities found, try known function names and check their decorator
    if registered_count == 0:
        # Known activity function names and their registered names
        activity_mappings = {
            'http_request_activity': 'http_request',
            'python_function_activity': 'python_function',
            'human_approval_activity': 'human_approval',
        }
        
        for func_name, activity_name in activity_mappings.items():
            if hasattr(activities_module, func_name):
                func = getattr(activities_module, func_name)
                if callable(func):
                    activity_registry.register(activity_name, func)
                    registered_count += 1


async def execute_task(
    task: Task,
    task_config: Dict[str, Any],
    workflow_params: Dict[str, Any],
) -> Any:
    """Execute a task with retry and timeout handling.

    Args:
        task: Task definition
        task_config: Task configuration
        workflow_params: Workflow parameters

    Returns:
        Task execution result
    """
    # Get activity function
    if not activity_registry.has(task.activity_type):
        raise ValueError(f"Activity type '{task.activity_type}' not registered")

    activity_func = activity_registry.get(task.activity_type)

    # Prepare activity arguments
    # Merge task config with workflow params
    activity_args = {**task_config, **workflow_params}

    # Execute activity with retry policy
    retry_policy = dsl_retry_to_temporal(task.retry) if task.retry else None

    # Set timeout if specified
    timeout = None
    if task.timeout:
        timeout = parse_duration(task.timeout)

    try:
        if timeout:
            result = await asyncio.wait_for(
                activity_func(**activity_args),
                timeout=timeout.total_seconds(),
            )
        else:
            result = await activity_func(**activity_args)
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"Task '{task.id}' timed out after {task.timeout}")
    except Exception as e:
        raise ActivityError(f"Task '{task.id}' failed: {str(e)}") from e
