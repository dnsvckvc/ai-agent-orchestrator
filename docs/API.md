# API Documentation

## Overview

The Orchestrator exposes both gRPC and REST APIs for task management.

## gRPC API

### OrchestratorService

#### SubmitTask

Submit a new task for orchestration.

**Request**:
```protobuf
message TaskRequest {
  string task_id = 1;
  string task_type = 2;
  map<string, string> metadata = 3;
  repeated Input inputs = 4;
  ExecutionMode execution_mode = 5;
  int32 priority = 6;
  int64 timeout_ms = 7;
}
```

**Response**:
```protobuf
message TaskResponse {
  string task_id = 1;
  TaskStatus status = 2;
  string message = 3;
  int64 estimated_completion_ms = 4;
}
```

**Example** (Python):
```python
import grpc
from grpc_services.generated import orchestrator_pb2, orchestrator_pb2_grpc

channel = grpc.insecure_channel('localhost:50051')
stub = orchestrator_pb2_grpc.OrchestratorServiceStub(channel)

request = orchestrator_pb2.TaskRequest(
    task_id="task-001",
    task_type="report_generation",
    execution_mode=orchestrator_pb2.SEQUENTIAL,
    priority=5,
    timeout_ms=30000
)

response = stub.SubmitTask(request)
print(f"Task submitted: {response.task_id}, status: {response.status}")
```

#### GetTaskStatus

Get current status of a task.

**Request**:
```protobuf
message TaskStatusRequest {
  string task_id = 1;
}
```

**Response**:
```protobuf
message TaskStatusResponse {
  string task_id = 1;
  TaskStatus status = 2;
  repeated AgentExecution agent_executions = 3;
  Output output = 4;
  Error error = 5;
  TaskMetrics metrics = 6;
}
```

#### StreamTaskUpdates

Stream real-time updates for a task.

**Request**:
```protobuf
message TaskStatusRequest {
  string task_id = 1;
}
```

**Response** (stream):
```protobuf
message TaskUpdate {
  string task_id = 1;
  TaskStatus status = 2;
  string agent_id = 3;
  string message = 4;
  int32 progress_percent = 5;
  int64 timestamp_ms = 6;
}
```

**Example**:
```python
for update in stub.StreamTaskUpdates(request):
    print(f"Progress: {update.progress_percent}%, Status: {update.status}")
```

#### CancelTask

Cancel a running task.

**Request**:
```protobuf
message TaskCancelRequest {
  string task_id = 1;
  string reason = 2;
}
```

**Response**:
```protobuf
message TaskCancelResponse {
  bool success = 1;
  string message = 2;
}
```

## REST API (HTTP)

### Submit Task

```http
POST /api/v1/tasks
Content-Type: application/json

{
  "task_id": "task-001",
  "task_type": "report_generation",
  "inputs": [
    {
      "input_id": "input-1",
      "type": "text",
      "data": "Sample data"
    }
  ],
  "execution_mode": "sequential",
  "priority": 5,
  "timeout_ms": 30000,
  "metadata": {
    "report_title": "My Report"
  }
}
```

**Response**:
```json
{
  "task_id": "task-001",
  "status": "queued",
  "message": "Task submitted successfully",
  "estimated_completion_ms": 3000
}
```

### Get Task Status

```http
GET /api/v1/tasks/{task_id}
```

**Response**:
```json
{
  "task_id": "task-001",
  "status": "completed",
  "agent_executions": [
    {
      "agent_id": "agent-data-ingest-1",
      "agent_type": "data_ingest",
      "status": "completed",
      "execution_time_ms": 150
    }
  ],
  "output": {
    "type": "json_report",
    "data": {...}
  },
  "metrics": {
    "total_duration_ms": 450,
    "queue_time_ms": 50,
    "execution_time_ms": 400,
    "retry_count": 0,
    "agents_used": 3
  }
}
```

### Cancel Task

```http
DELETE /api/v1/tasks/{task_id}
Content-Type: application/json

{
  "reason": "User requested cancellation"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Task cancelled successfully"
}
```

### Health Check

```http
GET /health
```

**Response**:
```json
{
  "healthy": true,
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "stats": {
    "active_tasks": 42,
    "metrics": {...}
  }
}
```

### Metrics Endpoint

```http
GET /metrics
```

**Response** (Prometheus format):
```
# TYPE tasks_submitted_total counter
tasks_submitted_total 1523

# TYPE tasks_completed_total counter
tasks_completed_total 1489

# TYPE task_execution_time_ms summary
task_execution_time_ms{quantile="0.5"} 245
task_execution_time_ms{quantile="0.95"} 420
task_execution_time_ms{quantile="0.99"} 480
```

## Task Types

### report_generation

Generates analytical reports from multi-modal data.

**Inputs**: Text, Images, JSON
**Execution Mode**: SEQUENTIAL (recommended)
**Agents Used**: data_ingest → data_analysis → synthesis

### real_time_monitoring

Processes video streams for object detection and alerting.

**Inputs**: Video streams
**Execution Mode**: SEQUENTIAL or PARALLEL
**Agents Used**: video_detection → alerting

### data_analysis

Performs data analysis on structured/unstructured data.

**Inputs**: JSON, Text
**Execution Mode**: PARALLEL (recommended)
**Agents Used**: data_analysis

### api_call

Makes external API calls with retry logic.

**Inputs**: JSON payloads
**Execution Mode**: PARALLEL
**Agents Used**: api_caller

## Execution Modes

### SEQUENTIAL

Agents execute one after another, output of one feeds into next.

**Use Case**: Pipelines (data ingest → analysis → synthesis)

### PARALLEL

All agents execute concurrently.

**Use Case**: Independent operations, maximum throughput

### HYBRID

Combination of parallel and sequential execution.

**Use Case**: Complex workflows with mixed dependencies

## Error Handling

### Error Codes

- `VALIDATION_ERROR`: Invalid input
- `AGENT_UNAVAILABLE`: No healthy agents available
- `EXECUTION_FAILED`: Task execution failed
- `TIMEOUT`: Task exceeded timeout
- `CANCELLED`: Task cancelled by user

### Retryable Errors

The system automatically retries these errors:
- Connection errors
- Timeout errors (with exponential backoff)
- Transient agent failures

Maximum retries: 3

## Rate Limiting

Default limits:
- 1000 requests/second per orchestrator instance
- Auto-scaling triggers at 70% CPU utilization

## Authentication

For production deployments, implement one of:
- API Keys (Header: `X-API-Key`)
- JWT Tokens (Header: `Authorization: Bearer <token>`)
- mTLS for gRPC

## Examples

See `examples/` directory for complete examples:
- `examples/report_generation.py`
- `examples/real_time_monitoring.py`
- `examples/streaming_updates.py`
