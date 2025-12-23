"""Temporal worker for executing workflows."""

import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker

from workflow_engine.core.workflows import WorkflowEngineWorkflow
from workflow_engine.core.task_executor import activity_registry
# Import activities package to trigger automatic registration of all activities
# All Python files in workflow_engine/core/activities/ will be automatically discovered and registered
from workflow_engine.core import activities as _activities  # noqa: F401
from workflow_engine.storage.database import init_db
from workflow_engine.core.workflow_registry import register_all_workflows


async def main():
    """Run Temporal worker."""
    # Initialize database connection (required for activities that need DB access)
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://workflow:workflow@localhost:5433/workflow_engine",
    )
    async_database_url = os.getenv(
        "ASYNC_DATABASE_URL",
        database_url.replace("postgresql://", "postgresql+asyncpg://"),
    )
    init_db(database_url, async_database_url)
    print("Database initialized for worker")
    
    # Auto-register workflows from workflows directory
    print("Registering workflows from workflows directory...")
    registration_results = await register_all_workflows()
    print(
        f"Workflow registration: {registration_results['registered']} registered, "
        f"{registration_results['updated']} updated, {registration_results['failed']} failed"
    )
    
    # Connect to Temporal
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost")
    temporal_port = int(os.getenv("TEMPORAL_PORT", "7233"))
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "workflow-engine")

    client = await Client.connect(
        f"{temporal_host}:{temporal_port}",
        namespace=namespace,
    )

    # Auto-discover activities from registry
    registered_activities = activity_registry.get_all_temporal_activities()

    if not registered_activities:
        print("Warning: No activities registered. Worker may not be able to execute tasks.")
    else:
        # Print registered activity names for debugging
        activity_names = []
        for activity_func in registered_activities:
            # Try to get the activity name from the decorator
            if hasattr(activity_func, '__temporal_activity__'):
                activity_name = activity_func.__temporal_activity__.name
                activity_names.append(activity_name)
            else:
                activity_name = activity_func.__name__
                activity_names.append(activity_name)
        print(f"Registered activities: {', '.join(activity_names)}")

    # Create worker
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[WorkflowEngineWorkflow],
        activities=registered_activities,
    )

    print(f"Worker started on task queue: {task_queue}")
    print(f"Registered {len(registered_activities)} activity type(s)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

