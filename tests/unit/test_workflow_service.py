"""Unit tests for workflow service."""

import pytest
from uuid import uuid4

from workflow_engine.api.services import WorkflowService
from workflow_engine.storage.models import WorkflowDefinition, WorkflowExecutionStatus


@pytest.mark.asyncio
async def test_create_workflow(
    mock_workflow_repository,
    mock_execution_repository,
    mock_workflow_executor,
    sample_workflow_yaml,
):
    """Test creating a workflow."""
    import yaml
    from workflow_engine.dsl.parser import WorkflowParser
    
    service = WorkflowService(
        mock_workflow_repository,
        mock_execution_repository,
        mock_workflow_executor,
    )

    # Mock repository to return None (workflow doesn't exist)
    mock_workflow_repository.get_by_name.return_value = None
    
    # Mock create to return a workflow
    created_workflow = WorkflowDefinition(
        id=uuid4(),
        name="test-workflow",
        version="1.0",
        definition_yaml=yaml.dump(sample_workflow_yaml),
        definition_json=sample_workflow_yaml,
    )
    mock_workflow_repository.create.return_value = created_workflow

    workflow = await service.create_workflow(
        name="test-workflow",
        version="1.0",
        definition_yaml=yaml.dump(sample_workflow_yaml),
    )

    assert workflow.name == "test-workflow"
    mock_workflow_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_workflow_duplicate_name(
    mock_workflow_repository,
    mock_execution_repository,
    mock_workflow_executor,
    sample_workflow_yaml,
):
    """Test creating workflow with duplicate name fails."""
    import yaml
    
    service = WorkflowService(
        mock_workflow_repository,
        mock_execution_repository,
        mock_workflow_executor,
    )

    # Mock repository to return existing workflow
    existing = WorkflowDefinition(id=uuid4(), name="test-workflow", version="1.0", definition_yaml="", definition_json={})
    mock_workflow_repository.get_by_name.return_value = existing

    with pytest.raises(ValueError, match="already exists"):
        await service.create_workflow(
            name="test-workflow",
            version="1.0",
            definition_yaml=yaml.dump(sample_workflow_yaml),
        )


@pytest.mark.asyncio
async def test_execute_workflow(
    mock_workflow_repository,
    mock_execution_repository,
    mock_workflow_executor,
    sample_workflow_db_model,
):
    """Test executing a workflow."""
    service = WorkflowService(
        mock_workflow_repository,
        mock_execution_repository,
        mock_workflow_executor,
    )

    # Mock workflow exists
    mock_workflow_repository.get_by_id.return_value = sample_workflow_db_model
    
    # Mock execution creation
    from workflow_engine.storage.models import WorkflowExecution
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_definition_id=sample_workflow_db_model.id,
        workflow_definition_name=sample_workflow_db_model.name,
        status=WorkflowExecutionStatus.PENDING,
        parameters={},
    )
    mock_execution_repository.create.return_value = execution
    mock_execution_repository.update.return_value = execution

    result = await service.execute_workflow(sample_workflow_db_model.id, {"param": "value"})

    assert result.workflow_definition_id == sample_workflow_db_model.id
    mock_workflow_executor.start_workflow.assert_called_once()

