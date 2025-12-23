"""FastAPI application main file."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from workflow_engine.api.routes import workflows, executions, approvals
from workflow_engine.storage import database
from workflow_engine.storage.database import init_db, Base
# Import models to ensure they're registered with Base.metadata
from workflow_engine.storage.models import WorkflowDefinition, WorkflowExecution, ApprovalRequest, ApprovalRequest
from workflow_engine.core.workflow_registry import register_all_workflows


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://workflow:workflow@localhost:5433/workflow_engine",
    )
    async_database_url = os.getenv(
        "ASYNC_DATABASE_URL",
        database_url.replace("postgresql://", "postgresql+asyncpg://"),
    )
    
    init_db(database_url, async_database_url)
    
    # Create tables automatically on startup
    # Access sync_engine from the module after init_db() has set it
    if database.sync_engine:
        Base.metadata.create_all(bind=database.sync_engine)
    
    # Auto-register workflows from workflows directory
    registration_results = await register_all_workflows()
    print(
        f"Workflow registration: {registration_results['registered']} registered, "
        f"{registration_results['updated']} updated, {registration_results['failed']} failed"
    )
    
    yield
    
    # Shutdown
    pass


app = FastAPI(
    title="Workflow Engine API",
    description="Core workflow engine with Temporal orchestration",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workflows.router)
app.include_router(executions.router)
app.include_router(approvals.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Workflow Engine API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

