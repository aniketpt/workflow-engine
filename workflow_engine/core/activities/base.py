"""Base activity implementations for workflow tasks.

This module contains core activities like http_request, python_function, and human_approval.
Activities are automatically registered via the activities package __init__.py.
"""

import httpx
from typing import Any, Dict
from temporalio import activity


@activity.defn(name="http_request")
async def http_request_activity(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute HTTP request activity.

    Args:
        args: Dictionary containing activity arguments:
            - url: Request URL (required)
            - method: HTTP method (default: "GET")
            - headers: Request headers
            - body: Request body
            - timeout: Request timeout in seconds (default: 30.0)
            - simulate_failure: If True (in body or top-level), raises an exception (for testing)

    Returns:
        Response data
    """
    url = args.get("url")
    method = args.get("method", "GET")
    headers = args.get("headers")
    body = args.get("body")
    timeout = args.get("timeout", 30.0)
    
    # Check for simulate_failure flag (can be in body or top-level args)
    simulate_failure = args.get("simulate_failure", False)
    if isinstance(body, dict):
        # Check body for simulate_failure (handles boolean True, string "true"/"True", etc.)
        body_simulate = body.get("simulate_failure", False)
        if isinstance(body_simulate, bool):
            simulate_failure = simulate_failure or body_simulate
        elif isinstance(body_simulate, str):
            body_simulate = body_simulate.lower() in ("true", "1", "yes")
            simulate_failure = simulate_failure or body_simulate
    
    # Convert string booleans to actual booleans
    if isinstance(simulate_failure, str):
        simulate_failure = simulate_failure.lower() in ("true", "1", "yes")
    
    # If simulate_failure is True, raise an exception to trigger compensation
    if simulate_failure:
        raise ValueError("Simulated failure: simulate_failure flag was set to true")
    
    if headers is None:
        headers = {}

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=body if body else None,
        )
        response.raise_for_status()
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
        }


@activity.defn(name="python_function")
async def python_function_activity(
    args: Dict[str, Any],
) -> Any:
    """Execute Python function activity.

    Note: This is a placeholder. In production, you'd want to securely
    execute user-defined functions, possibly in a sandboxed environment.

    Args:
        args: Dictionary containing activity arguments:
            - function_name: Function name to execute (required)
            - args: Positional arguments
            - kwargs: Keyword arguments

    Returns:
        Function result
    """
    function_name = args.get("function_name")
    func_args = args.get("args")
    func_kwargs = args.get("kwargs")
    
    # This is a placeholder - in production, implement secure function execution
    raise NotImplementedError("Python function activities not yet implemented. Use http_request for now.")


@activity.defn(name="human_approval")
async def human_approval_activity(
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """Wait for human approval activity.
    
    Creates an approval request in the database and polls until approved/rejected or timeout.
    Use the API endpoints to list pending approvals and approve/reject them.
    
    Args:
        args: Dictionary containing activity arguments:
            - approval_id: Approval ID (required)
            - title: Human-readable title for the approval request
            - description: Description of what needs approval
            - context: Additional context data (dict)
            - poll_interval: How often to poll in seconds (default: 5s)
            - max_wait_time: Maximum time to wait in seconds (default: 1 hour)
            - workflow_execution_id: Optional workflow execution ID for linking
            - task_id: Optional task ID that requested approval
        
    Returns:
        Approval result with status and optional comment
    """
    import asyncio
    import time
    from datetime import datetime, timedelta
    from uuid import UUID
    from workflow_engine.storage.database import get_async_session
    from workflow_engine.storage.models import ApprovalRequest, ApprovalStatus
    from workflow_engine.storage.repositories import SQLAlchemyApprovalRepository
    
    approval_id = args.get("approval_id")
    title = args.get("title")
    description = args.get("description")
    context = args.get("context")
    poll_interval = args.get("poll_interval", 5.0)
    max_wait_time = args.get("max_wait_time", 3600.0)
    workflow_execution_id = args.get("workflow_execution_id")
    task_id = args.get("task_id")
    
    if not approval_id:
        raise ValueError("approval_id is required")
    
    # Make approval_id unique by appending execution_id if available
    # This ensures each workflow execution gets a unique approval_id
    # This prevents conflicts when multiple workflows use the same base approval_id
    if workflow_execution_id and not approval_id.endswith(f"-{workflow_execution_id}"):
        approval_id = f"{approval_id}-{workflow_execution_id}"
    elif not workflow_execution_id:
        # Fallback: if no execution_id available, append a UUID to ensure uniqueness
        import uuid
        approval_id = f"{approval_id}-{uuid.uuid4()}"
    
    title = title or f"Approval Request: {approval_id}"
    
    # Create approval request in database
    async for session in get_async_session():
        approval_repo = SQLAlchemyApprovalRepository(session)
        
        # Look up execution by temporal_workflow_id to get the actual execution ID
        # The workflow_execution_id passed might be extracted from workflow ID, but we need the DB ID
        from workflow_engine.storage.repositories import SQLAlchemyExecutionRepository
        execution_repo = SQLAlchemyExecutionRepository(session)
        current_execution_uuid = None
        
        if workflow_execution_id:
            # Try to find execution by the extracted ID first
            try:
                execution = await execution_repo.get_by_id(UUID(workflow_execution_id))
                if execution:
                    current_execution_uuid = execution.id
            except (ValueError, TypeError):
                pass
            
            # If not found, try looking up by temporal_workflow_id
            if not current_execution_uuid:
                temporal_workflow_id = f"workflow-{workflow_execution_id}"
                execution = await execution_repo.get_by_temporal_id(temporal_workflow_id)
                if execution:
                    current_execution_uuid = execution.id
        
        # Check if approval already exists
        # Note: approval_id is already made unique above by appending execution_id
        existing = await approval_repo.get_by_approval_id(approval_id)
        
        # If approval exists and is for this execution and still pending, reuse it
        # Otherwise, create a new one
        if existing and existing.workflow_execution_id == current_execution_uuid and existing.status == ApprovalStatus.PENDING:
            approval = existing
        else:
            # Create new approval request
            # Only set workflow_execution_id if we found a valid execution in the database
            approval = ApprovalRequest(
                approval_id=approval_id,
                workflow_execution_id=current_execution_uuid,  # Use the looked-up execution ID, or None
                task_id=task_id,
                status=ApprovalStatus.PENDING,
                title=title,
                description=description,
                context=context or {},
                expires_at=datetime.utcnow() + timedelta(seconds=max_wait_time) if max_wait_time else None,
            )
            approval = await approval_repo.create(approval)
            await session.commit()
        break
    
    start_time = time.time()
    
    # Poll for approval status
    while (time.time() - start_time) < max_wait_time:
        try:
            async for session in get_async_session():
                approval_repo = SQLAlchemyApprovalRepository(session)
                approval = await approval_repo.get_by_approval_id(approval_id)
                
                if not approval:
                    raise ValueError(f"Approval request '{approval_id}' not found")
                
                # Check if approved or rejected
                if approval.status == ApprovalStatus.APPROVED:
                    await session.commit()
                    return {
                        "status": "approved",
                        "approval_id": approval_id,
                        "approved_by": approval.approved_by,
                        "approved_at": approval.responded_at.isoformat() if approval.responded_at else None,
                        "comment": approval.comment,
                    }
                elif approval.status == ApprovalStatus.REJECTED:
                    await session.commit()
                    raise ValueError(
                        f"Approval rejected: {approval.comment or 'No comment provided'}"
                    )
                elif approval.status == ApprovalStatus.TIMEOUT:
                    await session.commit()
                    raise TimeoutError(f"Approval timed out: {approval_id}")
                
                # Still pending - wait before next poll
                await session.commit()
                break
        except (ValueError, TimeoutError):
            raise
        except Exception:
            # Log error but continue polling
            pass
        
        # Wait before next poll
        await asyncio.sleep(poll_interval)
    
    # Timeout - mark as timeout and raise error
    async for session in get_async_session():
        approval_repo = SQLAlchemyApprovalRepository(session)
        approval = await approval_repo.get_by_approval_id(approval_id)
        if approval and approval.status == ApprovalStatus.PENDING:
            approval.status = ApprovalStatus.TIMEOUT
            approval.responded_at = datetime.utcnow()
            await approval_repo.update(approval)
            await session.commit()
        break
    
    raise TimeoutError(
        f"Approval timeout: approval_id '{approval_id}' not approved within {max_wait_time}s"
    )


@activity.defn(name="update_execution_status")
async def update_execution_status_activity(
    args: Dict[str, Any],
) -> None:
    """Update workflow execution status in database.
    
    This activity is called at the end of workflow execution (success or failure)
    to update the WorkflowExecution record in the database with the final status.
    
    Args:
        args: Dictionary containing activity arguments:
            - execution_id: Workflow execution ID (UUID string, required)
            - status: Execution status ("COMPLETED", "FAILED", etc.)
            - result: Optional workflow result (dict)
            - error: Optional error message (string)
    """
    from datetime import datetime
    from uuid import UUID
    from workflow_engine.storage.database import get_async_session
    from workflow_engine.storage.models import WorkflowExecutionStatus
    from workflow_engine.storage.repositories import SQLAlchemyExecutionRepository
    
    execution_id_str = args.get("execution_id")
    status_str = args.get("status")
    result = args.get("result")
    error = args.get("error")
    
    if not execution_id_str:
        raise ValueError("execution_id is required")
    
    if not status_str:
        raise ValueError("status is required")
    
    try:
        execution_id = UUID(execution_id_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid execution_id format: {execution_id_str}")
    
    try:
        status = WorkflowExecutionStatus(status_str)
    except ValueError:
        raise ValueError(f"Invalid status: {status_str}")
    
    async for session in get_async_session():
        execution_repo = SQLAlchemyExecutionRepository(session)
        
        # Update execution status
        updated = await execution_repo.update_status(
            execution_id=execution_id,
            status=status,
            result=result,
            error=error,
        )
        
        if not updated:
            raise ValueError(f"Execution not found: {execution_id}")
        
        # Also update completed_at timestamp if status is terminal
        if status in [WorkflowExecutionStatus.COMPLETED, WorkflowExecutionStatus.FAILED, WorkflowExecutionStatus.CANCELLED]:
            execution = await execution_repo.get_by_id(execution_id)
            if execution and not execution.completed_at:
                execution.completed_at = datetime.utcnow()
                await execution_repo.update(execution)
        
        await session.commit()
        break

