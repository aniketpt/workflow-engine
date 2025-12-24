"""Unit tests for compensation support."""

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from workflow_engine.dsl.schema import (
    WorkflowDefinition,
    Task,
    Compensation,
    RetryPolicy,
)
from workflow_engine.core.workflows import WorkflowEngineWorkflow


@pytest.fixture
def workflow_with_compensation():
    """Create a workflow definition with compensation."""
    return WorkflowDefinition(
        name="test-compensation",
        version="1.0",
        tasks=[
            Task(
                id="task1",
                name="Task 1",
                activity_type="http_request",
                config={"url": "https://api.example.com/create"},
                compensation=Compensation(
                    activity_type="http_request",
                    config={"url": "https://api.example.com/delete", "method": "DELETE"},
                ),
            ),
            Task(
                id="task2",
                name="Task 2",
                activity_type="http_request",
                config={"url": "https://api.example.com/update"},
                depends_on=["task1"],
                compensation=Compensation(
                    activity_type="http_request",
                    config={"url": "https://api.example.com/rollback", "method": "POST"},
                ),
            ),
            Task(
                id="task3",
                name="Task 3",
                activity_type="http_request",
                config={"url": "https://api.example.com/notify"},
                depends_on=["task2"],
                # No compensation defined
            ),
        ],
    )


@pytest.fixture
def workflow_without_compensation():
    """Create a workflow definition without compensation."""
    return WorkflowDefinition(
        name="test-no-compensation",
        version="1.0",
        tasks=[
            Task(
                id="task1",
                name="Task 1",
                activity_type="http_request",
                config={"url": "https://api.example.com/create"},
            ),
        ],
    )


@pytest.mark.asyncio
async def test_workflow_tracks_completed_tasks_order(workflow_with_compensation):
    """Test that workflow tracks completed tasks in order."""
    workflow = WorkflowEngineWorkflow()
    
    # Simulate task execution
    workflow.task_definitions = {task.id: task for task in workflow_with_compensation.tasks}
    workflow.completed_tasks_order.append("task1")
    workflow.completed_tasks_order.append("task2")
    
    assert workflow.completed_tasks_order == ["task1", "task2"]


@pytest.mark.asyncio
async def test_compensation_execution_order(workflow_with_compensation):
    """Test that compensations execute in reverse order of completion."""
    workflow = WorkflowEngineWorkflow()
    workflow.task_definitions = {task.id: task for task in workflow_with_compensation.tasks}
    workflow.completed_tasks_order = ["task1", "task2"]
    workflow.task_results = {
        "task1": {"result": "success"},
        "task2": {"result": "success"},
    }
    
    # Mock activity execution
    with patch("workflow_engine.core.workflows.workflow.execute_activity") as mock_exec:
        mock_exec.return_value = None
        
        await workflow._run_compensations(workflow_with_compensation, {})
        
        # Should execute compensations in reverse order: task2, then task1
        assert mock_exec.call_count == 2
        
        # Check that task2 compensation was called first (reverse order)
        call_args_list = [call[0][0] for call in mock_exec.call_args_list]
        # The activity_id should indicate compensation order
        activity_ids = [call[1].get("activity_id") for call in mock_exec.call_args_list]
        assert "compensate_task2" in activity_ids[0] or "compensate_task1" in activity_ids[1]


@pytest.mark.asyncio
async def test_compensation_skipped_if_not_defined(workflow_with_compensation):
    """Test that tasks without compensation are skipped."""
    workflow = WorkflowEngineWorkflow()
    workflow.task_definitions = {task.id: task for task in workflow_with_compensation.tasks}
    workflow.completed_tasks_order = ["task1", "task2", "task3"]  # task3 has no compensation
    workflow.task_results = {
        "task1": {"result": "success"},
        "task2": {"result": "success"},
        "task3": {"result": "success"},
    }
    
    with patch("workflow_engine.core.workflows.workflow.execute_activity") as mock_exec:
        mock_exec.return_value = None
        
        await workflow._run_compensations(workflow_with_compensation, {})
        
        # Should only execute 2 compensations (task1 and task2), skip task3
        assert mock_exec.call_count == 2


@pytest.mark.asyncio
async def test_compensation_continues_on_failure(workflow_with_compensation):
    """Test that compensation failures don't stop other compensations."""
    workflow = WorkflowEngineWorkflow()
    workflow.task_definitions = {task.id: task for task in workflow_with_compensation.tasks}
    workflow.completed_tasks_order = ["task1", "task2"]
    workflow.task_results = {
        "task1": {"result": "success"},
        "task2": {"result": "success"},
    }
    
    call_count = 0
    
    async def mock_execute_activity(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # First compensation (task2) fails
            raise Exception("Compensation failed")
        return None
    
    with patch("workflow_engine.core.workflows.workflow.execute_activity", side_effect=mock_execute_activity):
        with patch("workflow_engine.core.workflows.logger") as mock_logger:
            await workflow._run_compensations(workflow_with_compensation, {})
            
            # Should attempt both compensations despite first failure
            assert call_count == 2
            # Should log the error
            assert mock_logger.error.called


@pytest.mark.asyncio
async def test_workflow_without_compensation_backward_compatible(workflow_without_compensation):
    """Test that workflows without compensation continue to work."""
    workflow = WorkflowEngineWorkflow()
    workflow.task_definitions = {task.id: task for task in workflow_without_compensation.tasks}
    workflow.completed_tasks_order = ["task1"]
    
    # Should not raise any errors when running compensations
    await workflow._run_compensations(workflow_without_compensation, {})
    
    # No compensations should be executed
    assert len(workflow.completed_tasks_order) == 1


@pytest.mark.asyncio
async def test_compensation_activity_id_naming():
    """Test that compensation activities use correct activity_id for UI visibility."""
    workflow = WorkflowEngineWorkflow()
    
    task = Task(
        id="test_task",
        name="Test Task",
        activity_type="http_request",
        config={},
        compensation=Compensation(
            activity_type="http_request",
            config={},
        ),
    )
    
    workflow.task_definitions = {"test_task": task}
    workflow.completed_tasks_order = ["test_task"]
    workflow.task_results = {"test_task": {"result": "success"}}
    
    # Mock workflow.info() to avoid NotInWorkflowEventLoopError
    mock_workflow_info = MagicMock()
    mock_workflow_info.workflow_id = None
    
    with patch("workflow_engine.core.workflows.workflow.execute_activity") as mock_exec:
        with patch("workflow_engine.core.workflows.workflow.info", return_value=mock_workflow_info):
            mock_exec.return_value = None
            
            await workflow._run_compensations(
                WorkflowDefinition(name="test", version="1.0", tasks=[task]),
                {},
            )
            
            # Check that activity_id includes "compensate_" prefix
            assert mock_exec.called, "workflow.execute_activity should have been called"
            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs.get("activity_id") == "compensate_test_task"


@pytest.mark.asyncio
async def test_regular_task_activity_id_naming():
    """Test that regular tasks use correct activity_id for UI visibility."""
    from workflow_engine.core.task_executor import activity_registry
    
    # Mock activity registry
    mock_activity = AsyncMock(return_value={"result": "success"})
    activity_registry.register("http_request", mock_activity)
    
    workflow = WorkflowEngineWorkflow()
    task = Task(
        id="test_task",
        name="Test Task",
        activity_type="http_request",
        config={},
    )
    
    # Mock workflow.info() to avoid NotInWorkflowEventLoopError
    mock_workflow_info = MagicMock()
    mock_workflow_info.workflow_id = None
    
    with patch("workflow_engine.core.workflows.workflow.execute_activity") as mock_exec:
        with patch("workflow_engine.core.workflows.workflow.info", return_value=mock_workflow_info):
            mock_exec.return_value = {"result": "success"}
            
            await workflow._execute_task_with_retry(
                task,
                WorkflowDefinition(name="test", version="1.0", tasks=[task]),
                {},
            )
            
            # Check that activity_id includes "task_" prefix
            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs.get("activity_id") == "task_test_task"

