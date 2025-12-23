"""Pydantic schemas for API requests and responses."""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from workflow_engine.storage.models import WorkflowExecutionStatus, ApprovalStatus


# Workflow Schemas
class WorkflowCreateRequest(BaseModel):
    """Request to create a workflow."""

    name: str
    version: str = "1.0"
    description: Optional[str] = None
    definition_yaml: str = Field(..., description="YAML workflow definition")


class WorkflowUpdateRequest(BaseModel):
    """Request to update a workflow."""

    version: Optional[str] = None
    description: Optional[str] = None
    definition_yaml: Optional[str] = None


class WorkflowResponse(BaseModel):
    """Workflow response."""

    id: UUID
    name: str
    version: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    """List of workflows response."""

    workflows: List[WorkflowResponse]
    total: int


# Execution Schemas
class ExecutionCreateRequest(BaseModel):
    """Request to create/trigger an execution."""

    parameters: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    """Execution response."""

    id: UUID
    workflow_definition_id: UUID
    workflow_definition_name: str
    status: WorkflowExecutionStatus
    temporal_workflow_id: Optional[str]
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionListResponse(BaseModel):
    """List of executions response."""

    executions: List[ExecutionResponse]
    total: int


class ExecutionStatusResponse(BaseModel):
    """Execution status response."""

    id: UUID
    status: WorkflowExecutionStatus
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Approval Schemas
class ApprovalRequestResponse(BaseModel):
    """Approval request response."""

    id: UUID
    approval_id: str
    workflow_execution_id: Optional[UUID]
    task_id: Optional[str]
    status: ApprovalStatus
    title: Optional[str]
    description: Optional[str]
    context: Optional[Dict[str, Any]]
    approved_by: Optional[str]
    comment: Optional[str]
    created_at: datetime
    responded_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApprovalListResponse(BaseModel):
    """List of approval requests response."""

    approvals: List[ApprovalRequestResponse]
    total: int


class ApprovalActionRequest(BaseModel):
    """Request to approve or reject an approval."""

    approved: bool = Field(..., description="True to approve, False to reject")
    comment: Optional[str] = Field(None, description="Optional comment for approval/rejection")
    approved_by: Optional[str] = Field(None, description="Name/ID of person approving")

