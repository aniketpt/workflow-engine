"""Workflow state machine for managing execution states."""

from enum import Enum
from typing import Optional
from datetime import datetime


class WorkflowState(str, Enum):
    """Workflow execution states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskState(str, Enum):
    """Task execution states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StateTransition:
    """Represents a state transition."""

    def __init__(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        timestamp: Optional[datetime] = None,
    ):
        """Initialize state transition."""
        self.from_state = from_state
        self.to_state = to_state
        self.timestamp = timestamp or datetime.utcnow()

    def __repr__(self) -> str:
        return f"<StateTransition({self.from_state} -> {self.to_state} at {self.timestamp})>"


class WorkflowStateMachine:
    """State machine for workflow execution."""

    # Valid state transitions
    VALID_TRANSITIONS = {
        WorkflowState.PENDING: [WorkflowState.RUNNING, WorkflowState.CANCELLED],
        WorkflowState.RUNNING: [WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED],
        WorkflowState.COMPLETED: [],  # Terminal state
        WorkflowState.FAILED: [WorkflowState.RUNNING],  # Can retry
        WorkflowState.CANCELLED: [],  # Terminal state
    }

    def __init__(self, initial_state: WorkflowState = WorkflowState.PENDING):
        """Initialize state machine."""
        self.current_state = initial_state
        self.transitions: list[StateTransition] = []

    def can_transition(self, to_state: WorkflowState) -> bool:
        """Check if transition to target state is valid."""
        return to_state in self.VALID_TRANSITIONS.get(self.current_state, [])

    def transition(self, to_state: WorkflowState) -> bool:
        """Transition to new state if valid.

        Returns:
            True if transition was successful, False otherwise
        """
        if not self.can_transition(to_state):
            return False

        transition = StateTransition(self.current_state, to_state)
        self.transitions.append(transition)
        self.current_state = to_state
        return True

    def get_current_state(self) -> WorkflowState:
        """Get current state."""
        return self.current_state

    def get_transitions(self) -> list[StateTransition]:
        """Get all state transitions."""
        return self.transitions.copy()

