"""Service layer for workflow operations."""

from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from workflow_engine.dsl.parser import WorkflowParser
from workflow_engine.dsl.validator import WorkflowValidator
from workflow_engine.dsl.schema import WorkflowDefinition as DSLWorkflowDefinition
from workflow_engine.storage.models import WorkflowDefinition, WorkflowExecution, WorkflowExecutionStatus
from workflow_engine.storage.repositories import WorkflowRepository, ExecutionRepository
from workflow_engine.core.workflow_executor import WorkflowExecutor, TemporalWorkflowExecutor
from workflow_engine.core.workflows import WorkflowEngineWorkflow


class WorkflowService:
    """Service for workflow management."""

    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        execution_repo: ExecutionRepository,
        workflow_executor: WorkflowExecutor,
    ):
        """Initialize service with repositories and executor."""
        self.workflow_repo = workflow_repo
        self.execution_repo = execution_repo
        self.workflow_executor = workflow_executor

    async def create_workflow(
        self,
        name: str,
        version: str,
        definition_yaml: str,
        description: Optional[str] = None,
    ) -> WorkflowDefinition:
        """Create a new workflow definition.

        Args:
            name: Workflow name
            version: Workflow version
            definition_yaml: YAML workflow definition
            description: Optional description

        Returns:
            Created workflow definition

        Raises:
            ValueError: If workflow definition is invalid
        """
        # Parse and validate YAML
        dsl_workflow = WorkflowParser.parse_yaml(definition_yaml)
        errors = WorkflowValidator.validate(dsl_workflow)
        if errors:
            raise ValueError(f"Invalid workflow definition: {', '.join(errors)}")

        # Check if workflow with same name exists
        existing = await self.workflow_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Workflow with name '{name}' already exists")

        # Create database model
        workflow_def = WorkflowDefinition(
            id=uuid4(),
            name=name,
            version=version,
            description=description,
            definition_yaml=definition_yaml,
            definition_json=dsl_workflow.model_dump(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        return await self.workflow_repo.create(workflow_def)

    async def get_workflow(self, workflow_id: UUID) -> Optional[WorkflowDefinition]:
        """Get workflow by ID."""
        return await self.workflow_repo.get_by_id(workflow_id)

    async def list_workflows(self, skip: int = 0, limit: int = 100) -> list[WorkflowDefinition]:
        """List all workflows."""
        return await self.workflow_repo.list_all(skip=skip, limit=limit)

    async def update_workflow(
        self,
        workflow_id: UUID,
        version: Optional[str] = None,
        description: Optional[str] = None,
        definition_yaml: Optional[str] = None,
    ) -> Optional[WorkflowDefinition]:
        """Update workflow definition."""
        workflow_def = await self.workflow_repo.get_by_id(workflow_id)
        if not workflow_def:
            return None

        if definition_yaml:
            # Parse and validate new YAML
            dsl_workflow = WorkflowParser.parse_yaml(definition_yaml)
            errors = WorkflowValidator.validate(dsl_workflow)
            if errors:
                raise ValueError(f"Invalid workflow definition: {', '.join(errors)}")

            workflow_def.definition_yaml = definition_yaml
            workflow_def.definition_json = dsl_workflow.model_dump()

        if version:
            workflow_def.version = version
        if description is not None:
            workflow_def.description = description

        workflow_def.updated_at = datetime.utcnow()

        return await self.workflow_repo.update(workflow_def)

    async def delete_workflow(self, workflow_id: UUID) -> bool:
        """Delete workflow definition."""
        return await self.workflow_repo.delete(workflow_id)

    async def execute_workflow(
        self,
        workflow_id: UUID,
        parameters: Dict[str, Any],
    ) -> WorkflowExecution:
        """Execute a workflow.

        Args:
            workflow_id: Workflow definition ID
            parameters: Workflow parameters

        Returns:
            Created execution

        Raises:
            ValueError: If workflow not found or execution fails
        """
        # Get workflow definition
        workflow_def = await self.workflow_repo.get_by_id(workflow_id)
        if not workflow_def:
            raise ValueError(f"Workflow not found: {workflow_id}")

        # Parse workflow definition
        dsl_workflow = WorkflowParser.parse_yaml(workflow_def.definition_yaml)

        # Create execution record
        execution = WorkflowExecution(
            id=uuid4(),
            workflow_definition_id=workflow_id,
            workflow_definition_name=workflow_def.name,
            status=WorkflowExecutionStatus.PENDING,
            parameters=parameters,
            created_at=datetime.utcnow(),
        )

        execution = await self.execution_repo.create(execution)

        # Start Temporal workflow
        temporal_workflow_id = f"workflow-{execution.id}"
        try:
            result = await self.workflow_executor.start_workflow(
                workflow_type=WorkflowEngineWorkflow,
                workflow_id=temporal_workflow_id,
                task_queue="workflow-engine",
                args=(dsl_workflow, parameters),
            )

            # Update execution with Temporal ID
            execution.temporal_workflow_id = result
            execution.status = WorkflowExecutionStatus.RUNNING
            execution.started_at = datetime.utcnow()
            await self.execution_repo.update(execution)
        except Exception as e:
            execution.status = WorkflowExecutionStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
            await self.execution_repo.update(execution)
            raise ValueError(f"Failed to start workflow execution: {e}") from e

        return execution

    async def get_execution(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        return await self.execution_repo.get_by_id(execution_id)

    async def list_executions(
        self,
        workflow_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
        status: Optional[WorkflowExecutionStatus] = None,
    ) -> list[WorkflowExecution]:
        """List executions."""
        if workflow_id:
            return await self.execution_repo.list_by_workflow(workflow_id, skip=skip, limit=limit)
        return await self.execution_repo.list_all(skip=skip, limit=limit, status=status)

    async def cancel_execution(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Cancel a running execution."""
        execution = await self.execution_repo.get_by_id(execution_id)
        if not execution:
            return None

        if execution.status not in [WorkflowExecutionStatus.PENDING, WorkflowExecutionStatus.RUNNING]:
            raise ValueError(f"Cannot cancel execution in status: {execution.status}")

        if execution.temporal_workflow_id:
            try:
                await self.workflow_executor.cancel_workflow(execution.temporal_workflow_id)
            except Exception as e:
                raise ValueError(f"Failed to cancel workflow: {e}") from e

        execution.status = WorkflowExecutionStatus.CANCELLED
        execution.completed_at = datetime.utcnow()
        return await self.execution_repo.update(execution)

