# Activities Directory

This directory contains all activity implementations for the workflow engine. Activities are automatically discovered and registered when the worker starts.

## Adding New Activities

To add new activities, follow these steps:

1. **Create a new Python file** in this directory (e.g., `my_activities.py`)

2. **Define activity functions** decorated with `@activity.defn(name="activity_name")`:

```python
"""My custom activities."""

from typing import Any, Dict
from temporalio import activity


@activity.defn(name="my_activity")
async def my_activity(args: Dict[str, Any]) -> Dict[str, Any]:
    """My activity description.
    
    Args:
        args: Dictionary containing activity arguments
    
    Returns:
        Activity result
    """
    # Your activity implementation here
    return {"result": "success"}
```

3. **That's it!** The activity will be automatically discovered and registered when the worker starts.

## Activity Requirements

- Activities must be async functions
- Activities must accept a single `Dict[str, Any]` argument (named `args`)
- Activities must be decorated with `@activity.defn(name="activity_name")`
- The `name` parameter in the decorator is what will be used in workflow YAML files

## File Organization

- `base.py` - Core activities (http_request, python_function, human_approval)
- `openstack.py` - OpenStack VM provisioning activities
- Add your new activity files here following the naming convention

## Example

See `openstack.py` for examples of complex activities that interact with external systems.

## Testing

After adding activities, restart the worker to see them registered:

```bash
python -m workflow_engine.worker
```

You should see your new activities listed in the "Registered activities" output.

