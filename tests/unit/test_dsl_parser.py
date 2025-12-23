"""Unit tests for DSL parser."""

import pytest
import yaml
from pathlib import Path

from workflow_engine.dsl.parser import WorkflowParser
from workflow_engine.dsl.validator import WorkflowValidator
from workflow_engine.dsl.schema import WorkflowDefinition


def test_parse_valid_yaml():
    """Test parsing valid YAML workflow."""
    yaml_content = """
name: test-workflow
version: "1.0"
tasks:
  - id: task1
    name: "Test Task"
    type: activity
    activity_type: http_request
    config:
      url: "https://example.com"
"""
    workflow = WorkflowParser.parse_yaml(yaml_content)
    assert workflow.name == "test-workflow"
    assert len(workflow.tasks) == 1
    assert workflow.tasks[0].id == "task1"


def test_parse_invalid_yaml():
    """Test parsing invalid YAML."""
    yaml_content = "invalid: yaml: content: ["
    with pytest.raises(ValueError, match="Invalid YAML"):
        WorkflowParser.parse_yaml(yaml_content)


def test_parse_file(sample_workflow_yaml):
    """Test parsing from file."""
    # Create temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_workflow_yaml, f)
        temp_path = f.name

    try:
        workflow = WorkflowParser.parse_file(temp_path)
        assert workflow.name == "simple-workflow"
    finally:
        Path(temp_path).unlink()


def test_validate_workflow(sample_workflow_definition):
    """Test workflow validation."""
    errors = WorkflowValidator.validate(sample_workflow_definition)
    assert len(errors) == 0


def test_validate_circular_dependency():
    """Test validation detects circular dependencies."""
    yaml_content = """
name: circular-workflow
version: "1.0"
tasks:
  - id: task1
    name: "Task 1"
    type: activity
    activity_type: http_request
    config:
      url: "https://example.com"
    depends_on:
      - task2
  - id: task2
    name: "Task 2"
    type: activity
    activity_type: http_request
    config:
      url: "https://example.com"
    depends_on:
      - task1
"""
    with pytest.raises(ValueError, match="Circular dependency"):
        WorkflowParser.parse_yaml(yaml_content)


def test_validate_invalid_dependency():
    """Test validation detects invalid dependencies."""
    yaml_content = """
name: invalid-dependency
version: "1.0"
tasks:
  - id: task1
    name: "Task 1"
    type: activity
    activity_type: http_request
    config:
      url: "https://example.com"
    depends_on:
      - nonexistent_task
"""
    with pytest.raises(ValueError, match="unknown task"):
        WorkflowParser.parse_yaml(yaml_content)

