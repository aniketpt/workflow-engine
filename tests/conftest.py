"""Pytest configuration and fixtures."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from workflow_engine.dsl.schema import WorkflowDefinition as DSLWorkflowDefinition
from workflow_engine.storage.models import WorkflowDefinition, WorkflowExecution, WorkflowExecutionStatus
from workflow_engine.core.workflow_executor import WorkflowExecutor


@pytest.fixture
def sample_workflow_yaml():
    """Load sample workflow YAML."""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_workflows.yaml"
    with open(fixtures_path) as f:
        workflows = yaml.safe_load(f)
    return workflows["simple_workflow"]


@pytest.fixture
def sample_workflow_definition(sample_workflow_yaml):
    """Create a sample workflow definition."""
    from workflow_engine.dsl.parser import WorkflowParser
    return WorkflowParser.parse_yaml(yaml.dump(sample_workflow_yaml))


@pytest.fixture
def mock_workflow_repository():
    """Mock workflow repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_name = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_execution_repository():
    """Mock execution repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_temporal_id = AsyncMock()
    repo.list_by_workflow = AsyncMock(return_value=[])
    repo.list_all = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture
def mock_workflow_executor():
    """Mock workflow executor."""
    executor = AsyncMock(spec=WorkflowExecutor)
    executor.start_workflow = AsyncMock(return_value="temporal-workflow-id-123")
    executor.get_workflow_handle = AsyncMock()
    executor.get_workflow_result = AsyncMock()
    executor.cancel_workflow = AsyncMock()
    executor.signal_workflow = AsyncMock()
    return executor


@pytest.fixture
def sample_workflow_db_model(sample_workflow_definition):
    """Create a sample workflow database model."""
    from workflow_engine.dsl.parser import WorkflowParser
    return WorkflowDefinition(
        id=uuid4(),
        name=sample_workflow_definition.name,
        version=sample_workflow_definition.version,
        description=sample_workflow_definition.description,
        definition_yaml=WorkflowParser.to_yaml(sample_workflow_definition),
        definition_json=sample_workflow_definition.model_dump(mode='json'),
    )


@pytest.fixture
def sample_execution_db_model(sample_workflow_db_model):
    """Create a sample execution database model."""
    return WorkflowExecution(
        id=uuid4(),
        workflow_definition_id=sample_workflow_db_model.id,
        workflow_definition_name=sample_workflow_db_model.name,
        status=WorkflowExecutionStatus.PENDING,
        parameters={},
    )

