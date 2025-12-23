"""Database models for workflow definitions and executions."""

from datetime import datetime
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship
import enum

from workflow_engine.storage.database import Base

# Export Base for use in other modules
__all__ = ["Base", "WorkflowDefinition", "WorkflowExecution", "WorkflowExecutionStatus", "ApprovalRequest", "ApprovalStatus"]


class WorkflowExecutionStatus(str, enum.Enum):
    """Workflow execution status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, enum.Enum):
    """Approval request status."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


class WorkflowDefinition(Base):
    """Workflow definition model."""

    __tablename__ = "workflow_definitions"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    version = Column(String(50), nullable=False, default="1.0")
    description = Column(Text, nullable=True)
    definition_yaml = Column(Text, nullable=False)  # Raw YAML
    definition_json = Column(JSON, nullable=False)  # Parsed structure
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    executions = relationship("WorkflowExecution", back_populates="workflow_definition", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkflowDefinition(id={self.id}, name={self.name}, version={self.version})>"


class WorkflowExecution(Base):
    """Workflow execution model."""

    __tablename__ = "workflow_executions"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_definition_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_definition_name = Column(String(255), nullable=False, index=True)  # Denormalized for queries
    status = Column(
        SQLEnum(WorkflowExecutionStatus),
        nullable=False,
        default=WorkflowExecutionStatus.PENDING,
        index=True,
    )
    temporal_workflow_id = Column(String(255), nullable=True, unique=True, index=True)
    parameters = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship
    workflow_definition = relationship("WorkflowDefinition", back_populates="executions")

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, workflow={self.workflow_definition_name}, status={self.status})>"


class ApprovalRequest(Base):
    """Human approval request model."""

    __tablename__ = "approval_requests"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    approval_id = Column(String(255), unique=True, nullable=False, index=True)  # User-provided approval ID
    workflow_execution_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    task_id = Column(String(255), nullable=True)  # Task ID that requested approval
    status = Column(
        SQLEnum(ApprovalStatus),
        nullable=False,
        default=ApprovalStatus.PENDING,
        index=True,
    )
    title = Column(String(255), nullable=True)  # Human-readable title
    description = Column(Text, nullable=True)  # Approval request description
    context = Column(JSON, nullable=True)  # Additional context data
    approved_by = Column(String(255), nullable=True)  # Who approved/rejected
    comment = Column(Text, nullable=True)  # Approval/rejection comment
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    responded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration time

    # Relationship
    workflow_execution = relationship("WorkflowExecution", foreign_keys=[workflow_execution_id])

    def __repr__(self) -> str:
        return f"<ApprovalRequest(id={self.id}, approval_id={self.approval_id}, status={self.status})>"

