"""Workflow execution routes."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query

from workflow_engine.api.schemas import (
    ExecutionCreateRequest,
    ExecutionResponse,
    ExecutionListResponse,
    ExecutionStatusResponse,
)
from workflow_engine.api.services import WorkflowService
from workflow_engine.storage.models import WorkflowExecutionStatus
from workflow_engine.storage.database import get_async_session
from workflow_engine.storage.repositories import (
    SQLAlchemyWorkflowRepository,
    SQLAlchemyExecutionRepository,
)
from workflow_engine.core.workflow_executor import TemporalWorkflowExecutor, create_temporal_client

router = APIRouter(prefix="/executions", tags=["executions"])


async def get_workflow_service():
    """Dependency to get workflow service."""
    async for session in get_async_session():
        workflow_repo = SQLAlchemyWorkflowRepository(session)
        execution_repo = SQLAlchemyExecutionRepository(session)
        
        # Create Temporal client (in production, this should be a singleton)
        temporal_client = await create_temporal_client()
        workflow_executor = TemporalWorkflowExecutor(temporal_client)
        
        yield WorkflowService(workflow_repo, execution_repo, workflow_executor)
        break


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def execute_workflow(
    workflow_id: UUID,
    request: ExecutionCreateRequest,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Trigger workflow execution."""
    try:
        execution = await service.execute_workflow(workflow_id, request.parameters)
        return ExecutionResponse.model_validate(execution)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("", response_model=ExecutionListResponse)
async def list_executions(
    workflow_id: Optional[UUID] = Query(None, description="Filter by workflow ID"),
    status_filter: Optional[WorkflowExecutionStatus] = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: WorkflowService = Depends(get_workflow_service),
):
    """List all executions with optional filters."""
    executions = await service.list_executions(
        workflow_id=workflow_id,
        skip=skip,
        limit=limit,
        status=status_filter,
    )
    return ExecutionListResponse(
        executions=[ExecutionResponse.model_validate(e) for e in executions],
        total=len(executions),
    )


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get execution by ID."""
    execution = await service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return ExecutionResponse.model_validate(execution)


@router.get("/{execution_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: UUID,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get execution status."""
    execution = await service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return ExecutionStatusResponse.model_validate(execution)


@router.post("/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Cancel a running execution."""
    try:
        execution = await service.cancel_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        return ExecutionResponse.model_validate(execution)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

