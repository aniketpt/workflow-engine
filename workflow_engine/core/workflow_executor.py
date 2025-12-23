"""Workflow executor interface and Temporal implementation."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from uuid import UUID

from temporalio.client import Client, WorkflowHandle
from temporalio.service import RPCError


class WorkflowExecutor(ABC):
    """Abstract interface for workflow execution."""

    @abstractmethod
    async def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str,
        task_queue: str,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a workflow execution.

        Args:
            workflow_type: Name of the workflow function
            workflow_id: Unique identifier for this workflow run
            task_queue: Task queue name
            args: Positional arguments for the workflow
            kwargs: Keyword arguments for the workflow

        Returns:
            Temporal workflow run ID
        """
        pass

    @abstractmethod
    async def get_workflow_handle(self, workflow_id: str) -> Any:
        """Get a handle to an existing workflow.

        Args:
            workflow_id: Temporal workflow ID

        Returns:
            Workflow handle
        """
        pass

    @abstractmethod
    async def get_workflow_result(self, workflow_id: str, timeout: Optional[float] = None) -> Any:
        """Get the result of a completed workflow.

        Args:
            workflow_id: Temporal workflow ID
            timeout: Optional timeout in seconds

        Returns:
            Workflow result
        """
        pass

    @abstractmethod
    async def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a running workflow.

        Args:
            workflow_id: Temporal workflow ID
        """
        pass

    @abstractmethod
    async def signal_workflow(
        self,
        workflow_id: str,
        signal_name: str,
        *args: Any,
    ) -> None:
        """Send a signal to a workflow.

        Args:
            workflow_id: Temporal workflow ID
            signal_name: Name of the signal
            *args: Signal arguments
        """
        pass


class TemporalWorkflowExecutor(WorkflowExecutor):
    """Temporal implementation of WorkflowExecutor."""

    def __init__(self, client: Client):
        """Initialize executor with Temporal client."""
        self.client = client

    async def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str,
        task_queue: str,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a workflow execution."""
        if kwargs is None:
            kwargs = {}
        try:
            # Temporal start_workflow signature: start_workflow(workflow, *args, id=None, task_queue=None, ...)
            # The workflow can be the class or a string name
            # Convert workflow_type to string if it's a class
            if isinstance(workflow_type, type):
                workflow_type_name = workflow_type.__name__
            else:
                workflow_type_name = workflow_type
            
            # Temporal's start_workflow only accepts 2-3 positional arguments total
            # Our workflow needs 2 arguments (workflow_def, parameters)
            # So we pass them as a single tuple argument
            # The workflow's run method will unpack the tuple
            if isinstance(workflow_type, type):
                workflow_to_start = workflow_type
            else:
                workflow_to_start = workflow_type_name
            
            handle = await self.client.start_workflow(
                workflow_to_start,
                args,  # Pass the tuple as a single argument
                id=workflow_id,
                task_queue=task_queue,
            )
            return handle.id
        except Exception as e:
            raise

    async def get_workflow_handle(self, workflow_id: str) -> WorkflowHandle:
        """Get a handle to an existing workflow."""
        return self.client.get_workflow_handle(workflow_id)

    async def get_workflow_result(self, workflow_id: str, timeout: Optional[float] = None) -> Any:
        """Get the result of a completed workflow."""
        handle = await self.get_workflow_handle(workflow_id)
        return await handle.result(timeout=timeout)

    async def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a running workflow."""
        handle = await self.get_workflow_handle(workflow_id)
        await handle.cancel()

    async def signal_workflow(
        self,
        workflow_id: str,
        signal_name: str,
        *args: Any,
    ) -> None:
        """Send a signal to a workflow."""
        handle = await self.get_workflow_handle(workflow_id)
        await handle.signal(signal_name, *args)


async def create_temporal_client(
    temporal_host: str = "localhost",
    temporal_port: int = 7233,
    namespace: str = "default",
) -> Client:
    """Create and return a Temporal client.

    Args:
        temporal_host: Temporal server host
        temporal_port: Temporal server port
        namespace: Temporal namespace

    Returns:
        Configured Temporal client
    """
    return await Client.connect(
        f"{temporal_host}:{temporal_port}",
        namespace=namespace,
    )

