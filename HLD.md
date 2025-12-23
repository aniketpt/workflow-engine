# High-Level Architecture Design (HLD)
## Workflow Engine

---

## 1. Overview

The Workflow Engine is a robust, durable workflow orchestration system built on Temporal. It enables declarative workflow definitions via YAML, supports complex task dependencies, human-in-the-loop approvals, and provides complete execution history with automatic recovery.

### Key Capabilities
- **Durable Execution**: Workflows survive crashes, restarts, and deployments
- **YAML-based DSL**: Declarative workflow definitions
- **Human Approvals**: Long-running workflows with human intervention
- **Task Orchestration**: Sequential and parallel task execution with dependencies
- **Retry & Timeout**: Configurable per-task retry policies and timeouts
- **Complete Audit Trail**: Full execution history and state tracking

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│                    (REST API Consumers)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Workflows   │  │  Executions  │  │  Approvals   │           │
│  │    Routes    │  │    Routes    │  │    Routes    │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
└─────────┼─────────────────┼──────────────────┼──────────────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer                                │
│              ┌───────────────────────────┐                      │
│              │   WorkflowService         │                      │
│              │  - CRUD Operations        │                      │
│              │  - Execution Management   │                      │
│              └───────────┬───────────────┘                      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   DSL Layer   │  │  Core Layer   │  │ Storage Layer │
│               │  │               │  │               │
│ ┌───────────┐ │  │ ┌───────────┐ │  │ ┌───────────┐ │
│ │  Parser   │ │  │ │ Workflow  │ │  │ │ Repository│ │
│ │ Validator │ │  │ │ Executor  │ │  │ │ Pattern   │ │
│ │  Schema   │ │  │ │ State     │ │  │ │ Models    │ │
│ └───────────┘ │  │ │ Machine   │ │  │ └───────────┘ │
│               │  │ │ Task      │ │  │               │
│               │  │ │ Executor  │ │  │               │
│               │  │ │ Registry  │ │  │               │
│               │  │ └───────────┘ │  │               │
└───────────────┘  └───────┬───────┘  └───────┬───────┘
                           │                  │
                           ▼                  ▼
              ┌───────────────────────────────────────┐
              │      Temporal Orchestration           │
              │  ┌──────────────┐  ┌──────────────┐   │
              │  │   Worker     │  │   Workflow   │   │
              │  │  (Activities)│  │  (Orchestr.) │   │
              │  └──────────────┘  └──────────────┘   │
              └───────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │   Temporal    │  │   Activities  │
│   Database    │  │    Server     │  │   Registry    │
└───────────────┘  └───────────────┘  └───────────────┘
```

---

## 3. Component Architecture

### 3.1 API Layer (`workflow_engine/api/`)

**Purpose**: RESTful interface for workflow management and execution.

**Components**:
- **Routes**: FastAPI routers for workflows, executions, and approvals
- **Schemas**: Pydantic models for request/response validation
- **Services**: Business logic orchestration

**Key Endpoints**:
- `POST /workflows` - Create workflow definition
- `GET /workflows` - List workflows
- `POST /executions/workflows/{id}/execute` - Execute workflow
- `GET /executions/{id}` - Get execution status
- `POST /approvals/{id}/approve` - Approve/reject human approval

### 3.2 Service Layer (`workflow_engine/api/services.py`)

**Purpose**: Business logic and orchestration between API and core components.

**Responsibilities**:
- Workflow CRUD operations
- Execution lifecycle management
- Validation and error handling
- Temporal workflow coordination

### 3.3 DSL Layer (`workflow_engine/dsl/`)

**Purpose**: Parse, validate, and manage YAML workflow definitions.

**Components**:
- **Parser**: YAML → Pydantic model conversion
- **Validator**: Workflow definition validation
- **Schema**: Pydantic models for workflow structure

**Workflow Definition Structure**:
```yaml
name: workflow-name
version: 1.0
description: "Workflow description"
tasks:
  - id: task1
    name: "Task Name"
    type: activity
    activity_type: http_request
    depends_on: []
    config: {...}
    retry: {...}
    timeout: "5m"
```

### 3.4 Core Layer (`workflow_engine/core/`)

**Purpose**: Workflow execution engine and state management.

**Components**:

#### 3.4.1 Workflow Executor (`workflow_executor.py`)
- Abstract interface for workflow execution
- Temporal implementation (`TemporalWorkflowExecutor`)
- Handles workflow lifecycle: start, cancel, signal, query

#### 3.4.2 Workflow Engine (`workflows.py`)
- Temporal workflow implementation (`WorkflowEngineWorkflow`)
- Task dependency resolution
- Parallel and sequential task execution
- Retry and timeout handling

#### 3.4.3 State Machine (`state_machine.py`)
- Workflow state transitions (PENDING → RUNNING → COMPLETED/FAILED)
- Task state management
- State transition validation

#### 3.4.4 Task Executor (`task_executor.py`)
- Activity registry for extensible activity system
- Duration parsing and retry policy conversion
- Activity auto-discovery

#### 3.4.5 Workflow Registry (`workflow_registry.py`)
- Auto-discovery of workflows from `workflows/` directory
- Automatic registration on startup
- Workflow version management

### 3.5 Storage Layer (`workflow_engine/storage/`)

**Purpose**: Data persistence using Repository pattern.

**Components**:
- **Models**: SQLAlchemy ORM models
  - `WorkflowDefinition`: Workflow metadata and YAML
  - `WorkflowExecution`: Execution records and status
  - `ApprovalRequest`: Human approval requests
- **Repositories**: Abstract interfaces and SQLAlchemy implementations
  - `WorkflowRepository`
  - `ExecutionRepository`
  - `ApprovalRepository`

**Database**: PostgreSQL with async SQLAlchemy support

### 3.6 Temporal Integration

**Purpose**: Durable workflow orchestration.

**Components**:
- **Worker** (`worker.py`): Temporal worker process
  - Registers workflows and activities
  - Polls Temporal for work
  - Executes activities
- **Workflow** (`core/workflows.py`): Temporal workflow definition
  - Orchestrates task execution
  - Manages state and dependencies
  - Handles retries and timeouts

**Temporal Services**:
- Temporal Server: Workflow orchestration engine
- Temporal UI: Workflow visualization and debugging

### 3.7 Activities (`workflow_engine/core/activities/`)

**Purpose**: Extensible activity system for task execution.

**Architecture**:
- Base activity interface
- Auto-registration via decorators
- Activity registry for discovery
- Built-in activities:
  - `http_request`: HTTP API calls
  - `python_function`: Python code execution
  - `human_approval`: Human-in-the-loop approvals

---

## 4. Data Flow

### 4.1 Workflow Registration Flow

```
1. YAML File (workflows/*.yaml)
   ↓
2. WorkflowRegistry.discover_workflow_files()
   ↓
3. WorkflowParser.parse_yaml()
   ↓
4. WorkflowValidator.validate()
   ↓
5. WorkflowService.create_workflow()
   ↓
6. WorkflowRepository.create()
   ↓
7. PostgreSQL (workflow_definitions table)
```

### 4.2 Workflow Execution Flow

```
1. API: POST /executions/workflows/{id}/execute
   ↓
2. WorkflowService.execute_workflow()
   ↓
3. ExecutionRepository.create() → PostgreSQL
   ↓
4. TemporalWorkflowExecutor.start_workflow()
   ↓
5. Temporal Server → WorkflowEngineWorkflow.run()
   ↓
6. Task Dependency Resolution
   ↓
7. Activity Execution (via Worker)
   ↓
8. State Updates → PostgreSQL
   ↓
9. Completion → ExecutionRepository.update()
```

### 4.3 Human Approval Flow

```
1. Workflow reaches human_approval activity
   ↓
2. Activity creates ApprovalRequest → PostgreSQL
   ↓
3. Workflow pauses (waits for signal)
   ↓
4. API: POST /approvals/{id}/approve
   ↓
5. ApprovalRepository.update()
   ↓
6. TemporalWorkflowExecutor.signal_workflow()
   ↓
7. Workflow resumes with approval result
```

---

## 5. Technology Stack

 Layer           | Technology
-----------------|-----------
 API Framework   | FastAPI
 Database ORM    | SQLAlchemy (async)
 Database        | PostgreSQL
 Workflow Engine | Temporal
 Language        | Python 3.10+
 Validation      | Pydantic
 Configuration   | YAML

---

## 6. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Tier                         │
│  ┌──────────────┐              ┌──────────────┐             │
│  │  API Server  │              │  Worker      │             │
│  │  (FastAPI)   │              │  (Temporal)  │             │
│  │  Port: 8000  │              │              │             │
│  └──────────────┘              └──────────────┘             │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │   Temporal    │  │  Temporal UI  │
│  Port: 5433   │  │   Port: 7233  │  │  Port: 8080   │
└───────────────┘  └───────────────┘  └───────────────┘
```

**Scaling Considerations**:
- API servers: Horizontal scaling (stateless)
- Workers: Horizontal scaling (Temporal task queue distribution)
- Database: Read replicas for query scaling
- Temporal: Built-in horizontal scaling

---
