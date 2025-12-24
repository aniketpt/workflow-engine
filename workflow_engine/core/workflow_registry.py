"""Workflow auto-registration from workflows directory."""

import logging
from pathlib import Path
from typing import List, Tuple

from workflow_engine.dsl.parser import WorkflowParser
from workflow_engine.dsl.validator import WorkflowValidator
from workflow_engine.storage.database import get_async_session
from workflow_engine.storage.repositories import (
    SQLAlchemyWorkflowRepository,
    SQLAlchemyExecutionRepository,
)
from workflow_engine.core.workflow_executor import TemporalWorkflowExecutor, create_temporal_client
from workflow_engine.api.services import WorkflowService

log = logging.getLogger(__name__)

# Get the workflows directory (project root / workflows)
_WORKFLOWS_DIR = Path(__file__).parent.parent.parent / "workflows"


def discover_workflow_files() -> List[Path]:
    """Discover all YAML workflow files in the workflows directory.
    
    Returns:
        List of Path objects for workflow YAML files
    """
    if not _WORKFLOWS_DIR.exists():
        log.warning(f"Workflows directory not found: {_WORKFLOWS_DIR}")
        return []
    
    workflow_files = list(_WORKFLOWS_DIR.glob("*.yaml"))
    log.info(f"Discovered {len(workflow_files)} workflow file(s) in {_WORKFLOWS_DIR}")
    return workflow_files


async def register_workflow_from_file(
    yaml_file: Path,
    workflow_service: WorkflowService,
) -> Tuple[bool, str]:
    """Register or update a workflow from a YAML file.
    
    Args:
        yaml_file: Path to workflow YAML file
        workflow_service: WorkflowService instance for registration
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Read YAML content
        yaml_content = yaml_file.read_text()
        
        # Parse and validate workflow
        workflow_def = WorkflowParser.parse_yaml(yaml_content)
        errors = WorkflowValidator.validate(workflow_def)
        
        if errors:
            error_msg = f"Validation errors: {', '.join(errors)}"
            log.error(f"Failed to validate workflow {yaml_file.name}: {error_msg}")
            return False, error_msg
        
        # Check if workflow already exists
        existing = await workflow_service.workflow_repo.get_by_name(workflow_def.name)
        if existing:
            # Update existing workflow
            try:
                updated = await workflow_service.update_workflow(
                    existing.id,
                    version=workflow_def.version,
                    definition_yaml=yaml_content,
                    description=workflow_def.description,
                )
                if updated:
                    log.info(f"Updated workflow '{workflow_def.name}' v{workflow_def.version} from {yaml_file.name}")
                    return True, f"Updated workflow '{workflow_def.name}'"
                else:
                    return False, f"Failed to update workflow '{workflow_def.name}'"
            except ValueError as e:
                log.error(f"Failed to update workflow {workflow_def.name}: {e}")
                return False, str(e)
        else:
            # Create new workflow
            try:
                created = await workflow_service.create_workflow(
                    name=workflow_def.name,
                    version=workflow_def.version,
                    definition_yaml=yaml_content,
                    description=workflow_def.description,
                )
                log.info(f"Registered workflow '{workflow_def.name}' v{workflow_def.version} from {yaml_file.name}")
                return True, f"Registered workflow '{workflow_def.name}'"
            except ValueError as e:
                log.error(f"Failed to register workflow {workflow_def.name}: {e}")
                return False, str(e)
                
    except FileNotFoundError:
        error_msg = f"Workflow file not found: {yaml_file}"
        log.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error processing {yaml_file.name}: {e}"
        log.error(error_msg, exc_info=True)
        return False, error_msg


async def register_all_workflows() -> dict:
    """Register all workflows from the workflows directory.
    
    This function:
    1. Discovers all YAML files in the workflows directory
    2. Parses and validates each workflow
    3. Registers new workflows or updates existing ones
    
    Returns:
        Dictionary with registration results:
        {
            "total": int,
            "registered": int,
            "updated": int,
            "failed": int,
            "details": List[dict]
        }
    """
    workflow_files = discover_workflow_files()
    
    if not workflow_files:
        log.info("No workflow files found to register")
        return {
            "total": 0,
            "registered": 0,
            "updated": 0,
            "failed": 0,
            "details": [],
        }
    
    # Create workflow service within a single session
    async for session in get_async_session():
        workflow_repo = SQLAlchemyWorkflowRepository(session)
        execution_repo = SQLAlchemyExecutionRepository(session)
        
        # Create Temporal client for workflow service
        temporal_client = await create_temporal_client()
        workflow_executor = TemporalWorkflowExecutor(temporal_client)
        
        workflow_service = WorkflowService(workflow_repo, execution_repo, workflow_executor)
        
        results = {
            "total": len(workflow_files),
            "registered": 0,
            "updated": 0,
            "failed": 0,
            "details": [],
        }
        
        # Register each workflow
        for yaml_file in workflow_files:
            success, message = await register_workflow_from_file(yaml_file, workflow_service)
            detail = {
                "file": yaml_file.name,
                "success": success,
                "message": message,
            }
            results["details"].append(detail)
            
            if success:
                # Check if it was an update or new registration
                # We can infer this from the message
                if "Updated" in message:
                    results["updated"] += 1
                else:
                    results["registered"] += 1
            else:
                results["failed"] += 1
        
        # Explicitly commit the session to ensure all changes are persisted
        # This is necessary because using 'break' with async for may exit before
        # the context manager's commit runs
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
        # Session will auto-commit on successful completion (via get_async_session context manager)
        break
    
    log.info(
        f"Workflow registration complete: {results['registered']} registered, "
        f"{results['updated']} updated, {results['failed']} failed out of {results['total']} total"
    )
    
    return results

