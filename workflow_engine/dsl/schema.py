"""Workflow DSL schema definitions."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ParameterType(str, Enum):
    """Parameter types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class Parameter(BaseModel):
    """Workflow parameter definition."""

    name: str
    type: ParameterType
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None


class RetryPolicy(BaseModel):
    """Retry policy configuration."""

    max_attempts: int = Field(default=3, ge=1)
    initial_interval: str = Field(default="1s")  # e.g., "1s", "5m"
    max_interval: str = Field(default="30s")
    multiplier: float = Field(default=2.0, ge=1.0)

    @field_validator("initial_interval", "max_interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        """Validate interval format."""
        if not v:
            raise ValueError("Interval cannot be empty")
        # Basic validation - should be number + unit (s, m, h)
        if not v[-1] in ["s", "m", "h"]:
            raise ValueError("Interval must end with s (seconds), m (minutes), or h (hours)")
        try:
            float(v[:-1])
        except ValueError:
            raise ValueError(f"Invalid interval format: {v}")
        return v


class Task(BaseModel):
    """Workflow task definition."""

    id: str
    name: str
    type: str = "activity"  # Currently only "activity" supported
    activity_type: str  # e.g., "http_request", "python_function"
    config: Dict[str, Any] = Field(default_factory=dict)
    depends_on: Optional[List[str]] = Field(default=None)
    retry: Optional[RetryPolicy] = None
    timeout: Optional[str] = None  # e.g., "5m", "1h"

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: Optional[str]) -> Optional[str]:
        """Validate timeout format."""
        if v is None:
            return v
        if not v[-1] in ["s", "m", "h"]:
            raise ValueError("Timeout must end with s (seconds), m (minutes), or h (hours)")
        try:
            float(v[:-1])
        except ValueError:
            raise ValueError(f"Invalid timeout format: {v}")
        return v


class WorkflowDefinition(BaseModel):
    """Workflow definition schema."""

    name: str
    version: str = "1.0"
    description: Optional[str] = None
    parameters: List[Parameter] = Field(default_factory=list)
    tasks: List[Task] = Field(min_length=1)

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version_to_string(cls, v: Any) -> str:
        """Coerce version to string (handles YAML parsing 1.0 as float)."""
        if isinstance(v, (int, float)):
            return str(v)
        return str(v) if v else "1.0"

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, tasks: List[Task]) -> List[Task]:
        """Validate task dependencies."""
        task_ids = {task.id for task in tasks}
        
        # Check for duplicate task IDs
        if len(task_ids) != len(tasks):
            raise ValueError("Duplicate task IDs found")

        # Validate dependencies
        for task in tasks:
            if task.depends_on:
                for dep_id in task.depends_on:
                    if dep_id not in task_ids:
                        raise ValueError(f"Task '{task.id}' depends on unknown task '{dep_id}'")
                    if dep_id == task.id:
                        raise ValueError(f"Task '{task.id}' cannot depend on itself")

        # Check for circular dependencies (simple check)
        # Build dependency graph and check for cycles
        graph: Dict[str, List[str]] = {task.id: [] for task in tasks}
        for task in tasks:
            if task.depends_on:
                graph[task.id] = task.depends_on

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for task_id in task_ids:
            if task_id not in visited:
                if has_cycle(task_id):
                    raise ValueError(f"Circular dependency detected in task '{task_id}'")

        return tasks

