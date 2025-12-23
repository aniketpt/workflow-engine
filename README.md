# Workflow Engine

A robust, reusable workflow engine built on Temporal for durable execution orchestration.

## Features

- **YAML-based workflow definitions** - Define workflows declaratively
- **Temporal orchestration** - Durable, reliable workflow execution that survives crashes
- **Task dependencies** - Sequential and parallel task execution
- **Human-in-the-loop** - Pause workflows for approvals (impossible with Celery)
- **Retry policies** - Configurable retry logic per task with exponential backoff
- **Timeouts** - Per-task timeout configuration
- **Complete execution history** - Full audit trail of workflow execution
- **REST API** - FastAPI-based API for workflow management

## Why Use This Engine?

This workflow engine is built on Temporal and provides capabilities that simple task queues like Celery cannot:

- **Durable Execution**: Workflows survive server crashes, restarts, and deployments
- **Human Approvals**: Pause workflows for hours or days waiting for human input
- **Complex Dependencies**: Easy parallel + sequential task orchestration
- **State Management**: Automatic state persistence and recovery
- **Workflow History**: Complete audit trail without manual logging

## Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose

### Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy environment file:
   ```bash
   cp .env.example .env
   ```

4. Start services (Temporal + PostgreSQL):
   ```bash
   docker-compose up -d
   ```

5. Wait for services to be ready (about 30 seconds)

6. Start the Temporal worker (in one terminal):
   ```bash
   python -m workflow_engine.worker
   ```

7. Start the API server (in another terminal):
   ```bash
   uvicorn workflow_engine.api.main:app --reload
   ```

The API will be available at `http://localhost:8000`

Temporal UI will be available at `http://localhost:8080`

API documentation will be available at `http://localhost:8000/docs`

## Usage

### Auto-Registration of Workflows

Workflows are automatically discovered and registered from the `workflows/` directory when the worker or API server starts. Simply place your YAML workflow files in the `workflows/` directory and they'll be registered automatically.

**No manual registration needed!** Just:
1. Add your workflow YAML file to `workflows/`
2. Restart the worker or API server
3. The workflow is automatically registered (or updated if it already exists)

See [workflows/README.md](workflows/README.md) for details.

### Demo Workflow

Try the included order processing workflow that demonstrates all key features:

```bash
# Workflows are auto-registered on startup, so no registration needed!
# Just execute with sample order data:
curl -X POST http://localhost:8000/executions/workflows/{workflow_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "order_id": "ORD-12345",
      "customer_id": "CUST-789",
      "order_amount": 1500.00,
      "items": [{"product_id": "PROD-1", "quantity": 2}],
      "payment_method": {"type": "credit_card", "last4": "1234"},
      "customer_email": "customer@example.com",
      "customer_phone": "+1234567890"
    }
  }'
```

See [DEMO_WORKFLOW.md](DEMO_WORKFLOW.md) for detailed documentation and examples.

### Creating a Custom Workflow

1. **Create a YAML file** in the `workflows/` directory:

```yaml
# workflows/my_workflow.yaml
name: my-workflow
version: 1.0
description: "My custom workflow"

tasks:
  - id: task1
    name: "Test Task"
    type: activity
    activity_type: http_request
    config:
      url: https://httpbin.org/get
      method: GET
```

2. **Restart the worker or API server** - the workflow will be automatically registered!

Alternatively, you can still register workflows manually via the API if needed.

### Executing a Workflow

```bash
curl -X POST http://localhost:8000/executions/workflows/{workflow_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {}
  }'
```

### Checking Execution Status

```bash
curl http://localhost:8000/executions/{execution_id}
```

### Viewing Workflow Execution

Open Temporal UI at `http://localhost:8080` to see workflow execution in real-time with complete history and state visualization.

## Project Structure

```
workflow-engine/
├── workflows/          # Workflow YAML definitions (auto-registered)
├── workflow_engine/
│   ├── core/           # Core workflow execution logic
│   ├── storage/        # Database models and repositories
│   ├── api/            # FastAPI application
│   └── dsl/            # YAML workflow parser
├── tests/              # Test suite
├── migrations/          # Alembic database migrations
└── docker-compose.yml  # Local development services
```

## Example Workflows

All example workflows are in the `workflows/` directory and are automatically registered on startup:

- **workflows/order_processing_workflow.yaml** - Complete e-commerce order processing with human approvals, parallel tasks, and robust retries
- **workflows/human_approval_workflow.yaml** - Expense approval workflow demonstrating human-in-the-loop pattern
- **workflows/sample.yaml** - Data processing pipeline with parallel execution

## Development

Run tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=workflow_engine
```

