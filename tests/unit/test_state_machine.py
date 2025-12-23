"""Unit tests for state machine."""

import pytest
from workflow_engine.core.state_machine import WorkflowStateMachine, WorkflowState


def test_initial_state():
    """Test initial state is PENDING."""
    sm = WorkflowStateMachine()
    assert sm.get_current_state() == WorkflowState.PENDING


def test_valid_transition():
    """Test valid state transition."""
    sm = WorkflowStateMachine()
    assert sm.transition(WorkflowState.RUNNING) is True
    assert sm.get_current_state() == WorkflowState.RUNNING


def test_invalid_transition():
    """Test invalid state transition."""
    sm = WorkflowStateMachine()
    # Cannot go directly from PENDING to COMPLETED
    assert sm.transition(WorkflowState.COMPLETED) is False
    assert sm.get_current_state() == WorkflowState.PENDING


def test_transition_history():
    """Test state transition history."""
    sm = WorkflowStateMachine()
    sm.transition(WorkflowState.RUNNING)
    sm.transition(WorkflowState.COMPLETED)
    
    transitions = sm.get_transitions()
    assert len(transitions) == 2
    assert transitions[0].from_state == WorkflowState.PENDING
    assert transitions[0].to_state == WorkflowState.RUNNING
    assert transitions[1].from_state == WorkflowState.RUNNING
    assert transitions[1].to_state == WorkflowState.COMPLETED

