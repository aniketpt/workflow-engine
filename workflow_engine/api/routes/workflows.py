"""Workflow management routes."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from workflow_engine.api.schemas import (
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    WorkflowResponse,
    WorkflowListResponse,
)
from workflow_engine.api.services import WorkflowService
from workflow_engine.storage.database import get_async_session
from workflow_engine.storage.repositories import (
    SQLAlchemyWorkflowRepository,
    SQLAlchemyExecutionRepository,
)
from workflow_engine.core.workflow_executor import TemporalWorkflowExecutor, create_temporal_client

router = APIRouter(prefix="/workflows", tags=["workflows"])


async def get_workflow_service():
    """Dependency to get workflow service."""
    async for session in get_async_session():
        workflow_repo = SQLAlchemyWorkflowRepository(session)
        execution_repo = SQLAlchemyExecutionRepository(session)
        
        # Create Temporal client (in production, this should be a singleton)
        temporal_client = await create_temporal_client()
        workflow_executor = TemporalWorkflowExecutor(temporal_client)
        
        yield WorkflowService(workflow_repo, execution_repo, workflow_executor)


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: WorkflowCreateRequest,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Create a new workflow definition."""
    try:
        workflow = await service.create_workflow(
            name=request.name,
            version=request.version,
            definition_yaml=request.definition_yaml,
            description=request.description,
        )
        return WorkflowResponse.model_validate(workflow)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    service: WorkflowService = Depends(get_workflow_service),
):
    """List all workflow definitions."""
    workflows = await service.list_workflows(skip=skip, limit=limit)
    return WorkflowListResponse(
        workflows=[WorkflowResponse.model_validate(w) for w in workflows],
        total=len(workflows),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get workflow definition by ID."""
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowResponse.model_validate(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    request: WorkflowUpdateRequest,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Update workflow definition."""
    try:
        workflow = await service.update_workflow(
            workflow_id=workflow_id,
            version=request.version,
            description=request.description,
            definition_yaml=request.definition_yaml,
        )
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return WorkflowResponse.model_validate(workflow)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    service: WorkflowService = Depends(get_workflow_service),
):
    """Delete workflow definition."""
    deleted = await service.delete_workflow(workflow_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

