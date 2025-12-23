"""YAML workflow parser."""

import yaml
from typing import Dict, Any
from pathlib import Path

from workflow_engine.dsl.schema import WorkflowDefinition


class WorkflowParser:
    """Parser for YAML workflow definitions."""

    @staticmethod
    def parse_yaml(yaml_content: str) -> WorkflowDefinition:
        """Parse YAML string into WorkflowDefinition.

        Args:
            yaml_content: YAML string containing workflow definition

        Returns:
            Parsed WorkflowDefinition

        Raises:
            ValueError: If YAML is invalid or doesn't match schema
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}") from e

        if not data:
            raise ValueError("Empty workflow definition")

        try:
            return WorkflowDefinition(**data)
        except Exception as e:
            raise ValueError(f"Invalid workflow definition: {e}") from e

    @staticmethod
    def parse_file(file_path: str | Path) -> WorkflowDefinition:
        """Parse YAML file into WorkflowDefinition.

        Args:
            file_path: Path to YAML file

        Returns:
            Parsed WorkflowDefinition

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or doesn't match schema
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")

        with open(path, "r") as f:
            yaml_content = f.read()

        return WorkflowParser.parse_yaml(yaml_content)

    @staticmethod
    def to_dict(workflow: WorkflowDefinition) -> Dict[str, Any]:
        """Convert WorkflowDefinition to dictionary.

        Args:
            workflow: WorkflowDefinition instance

        Returns:
            Dictionary representation
        """
        return workflow.model_dump()

    @staticmethod
    def to_yaml(workflow: WorkflowDefinition) -> str:
        """Convert WorkflowDefinition to YAML string.

        Args:
            workflow: WorkflowDefinition instance

        Returns:
            YAML string representation
        """
        # Use mode='json' to serialize enums as their values, not Python objects
        return yaml.dump(workflow.model_dump(mode='json'), default_flow_style=False, sort_keys=False)

