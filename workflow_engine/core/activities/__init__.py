"""Activity registry - automatically discovers and registers all activities.

This module automatically discovers all activity functions decorated with @activity.defn
in all Python files within this directory and registers them with the activity registry.

To add new activities:
1. Create a new Python file in this directory (e.g., `my_activities.py`)
2. Define activity functions decorated with @activity.defn(name="activity_name")
3. The activities will be automatically registered when the worker starts
"""

import importlib
from pathlib import Path
from typing import List

from workflow_engine.core.task_executor import auto_register_activities

# Get the directory containing this __init__.py file
_ACTIVITIES_DIR = Path(__file__).parent


def _discover_activity_modules() -> List[str]:
    """Discover all Python modules in the activities directory.
    
    Returns:
        List of module names (without .py extension) that can be imported
    """
    modules = []
    for file_path in _ACTIVITIES_DIR.glob("*.py"):
        if file_path.name == "__init__.py":
            continue
        module_name = file_path.stem
        modules.append(module_name)
    return modules


def register_all_activities():
    """Register all activities from all modules in this directory.
    
    This function:
    1. Discovers all Python files in the activities directory
    2. Imports each module
    3. Calls auto_register_activities for each module
    
    Returns:
        Dictionary mapping module names to lists of registered activity names
    """
    modules = _discover_activity_modules()
    registered_activities = {}
    
    for module_name in modules:
        try:
            # Import the module using the full path
            full_module_name = f"workflow_engine.core.activities.{module_name}"
            module = importlib.import_module(full_module_name)
            
            # Register activities in this module
            auto_register_activities(module)
            
            # Collect registered activity names from this module
            module_activity_names = []
            for name in dir(module):
                if name.startswith('_'):
                    continue
                obj = getattr(module, name, None)
                if obj and callable(obj) and hasattr(obj, '__temporal_activity__'):
                    activity_info = obj.__temporal_activity__
                    activity_name = activity_info.name if activity_info.name else name
                    module_activity_names.append(activity_name)
            
            if module_activity_names:
                registered_activities[module_name] = module_activity_names
            
        except ImportError as e:
            print(f"Warning: Failed to import activity module '{module_name}': {e}")
    return registered_activities


# Auto-register all activities when this module is imported
# This ensures activities are registered as soon as the activities package is imported
_registered_modules = register_all_activities()

