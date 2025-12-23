# Workflows Directory

This directory contains all workflow YAML definitions. Workflows in this directory are automatically discovered and registered when the worker or API server starts.

## Adding New Workflows

To add a new workflow:

1. **Create a YAML file** in this directory (e.g., `my_workflow.yaml`)

2. **Define your workflow** following the workflow DSL schema:

```yaml
name: my-workflow
version: 1.0
description: "My workflow description"

parameters:
  - name: param1
    type: string
    required: true
    description: "Parameter description"

tasks:
  - id: task1
    name: "Task Name"
    type: activity
    activity_type: http_request
    config:
      url: "https://example.com"
      method: GET
```

3. **That's it!** The workflow will be automatically registered when you restart the worker or API server.

## Workflow Registration

- Workflows are automatically registered on worker/API server startup
- If a workflow with the same name already exists, it will be updated
- Invalid workflows will log warnings but won't prevent other workflows from registering
- Workflow files must have `.yaml` extension

## Workflow Updates

When you modify a workflow YAML file:
1. Restart the worker or API server
2. The workflow will be automatically updated in the database
3. Existing executions continue with the original definition
4. New executions use the updated definition

## File Organization

- Place all workflow YAML files directly in this directory
- Use descriptive filenames (e.g., `order-processing.yaml`, `data-pipeline.yaml`)
- Keep workflow files focused on a single workflow definition

## Examples

See the included workflows:
- `order_processing_workflow.yaml` - E-commerce order processing with human approvals
- `human_approval_workflow.yaml` - Expense approval workflow
- `sample.yaml` - Data processing pipeline example

