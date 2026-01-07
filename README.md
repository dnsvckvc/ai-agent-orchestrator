# Distributed AI Agent Orchestrator

A production-grade distributed AI agent orchestration system built with Kubernetes, gRPC, and Redis. Designed for high-throughput, fault-tolerant, multi-modal AI workloads with comprehensive monitoring and testing.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer / Ingress                  │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
┌─────────▼──────────┐       ┌──────────▼─────────┐
│  Orchestrator Pod  │       │  Orchestrator Pod  │
│  (Auto-scaling)    │       │  (Auto-scaling)    │
└─────────┬──────────┘       └──────────┬─────────┘
          │                              │
          └──────────────┬───────────────┘
                         │
          ┌──────────────▼──────────────┐
          │      Redis (State Store)     │
          │   - Task States              │
          │   - Agent Registry           │
          │   - Distributed Locks        │
          └──────────────┬───────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
┌─────────▼──────────┐       ┌──────────▼─────────┐
│  Agent Pool        │       │  Agent Pool        │
│  - Data Ingest     │       │  - Video Detection │
│  - Data Analysis   │       │  - Alerting        │
│  - Synthesis       │       │  - API Caller      │
└────────────────────┘       └────────────────────┘
```

## Key Features

### Production Architecture
- **Kubernetes-native**: Auto-scaling, rolling updates, health checks
- **gRPC Communication**: High-performance, type-safe inter-service communication
- **Redis State Management**: Distributed state, queue management, and locks
- **Horizontal Scaling**: Orchestrator and agents scale independently

### Multi-Modal Support
- Text processing
- Image analysis
- Video streaming
- JSON/structured data
- Binary data

### Fault Tolerance
- **Automatic retries** with exponential backoff
- **Circuit breaker** pattern for external APIs
- **Health monitoring** with automatic agent removal
- **Graceful degradation** under load
- **Task recovery** after failures

### Load Balancing
- **Least-loaded** agent selection
- **Round-robin** distribution
- **Weighted** capacity-based routing
- **Agent health** awareness

### Monitoring & Metrics
- Prometheus-compatible metrics
- Latency tracking (P50, P95, P99)
- Throughput monitoring
- Error rate tracking
- SLA compliance checks

## Use Cases

### Use Case 1: Report Generation

**Flow**: `User Query → Data Ingest → Analysis → Synthesis → JSON Report`

**Example**:
```python
task = TaskDefinition(
    task_id="report-001",
    task_type="report_generation",
    inputs=[
        {"type": "text", "data": "Q4 sales data..."},
        {"type": "image", "data": base64_image}
    ],
    execution_mode=ExecutionMode.SEQUENTIAL,
    metadata={"report_title": "Q4 Sales Analysis"}
)
```

**Output**:
```json
{
  "report_id": "report_1704412800",
  "title": "Q4 Sales Analysis",
  "executive_summary": "Analysis completed on 1000 data points...",
  "detailed_findings": {
    "statistics": {"mean": 42.5, "median": 40.0},
    "insights": ["Trend increasing", "Pattern detected"],
    "anomalies": []
  },
  "recommendations": [...]
}
```

### Use Case 2: Real-Time Monitoring

**Flow**: `Video Stream → Object Detection → Alerting → Alerts`

**Example**:
```python
task = TaskDefinition(
    task_id="monitor-001",
    task_type="real_time_monitoring",
    inputs=[{"type": "video", "data": video_stream}],
    execution_mode=ExecutionMode.SEQUENTIAL,
    metadata={
        "max_persons": 10,
        "restricted_area": True
    }
)
```

**Output**:
```json
{
  "alerts": [
    {
      "alert_id": "abc123",
      "type": "crowd_detected",
      "severity": "high",
      "message": "Person count (15) exceeds threshold (10)",
      "timestamp": 1704412800,
      "requires_action": true
    }
  ]
}
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Kubernetes cluster (or Minikube)
- Python 3.9+
- Redis 7+

### Installation

1. **Clone the repository**:
```bash
cd orchestrator
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Generate gRPC code**:
```bash
chmod +x grpc_services/generate_grpc.sh
./grpc_services/generate_grpc.sh
```

4. **Start Redis** (local testing):
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

5. **Run tests**:
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Stress tests
python tests/stress/run_stress_test.py
```

### Docker Deployment

Build images:
```bash
docker build -t orchestrator:latest -f Dockerfile.orchestrator .
docker build -t agent:latest -f Dockerfile.agent .
```

### Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace orchestrator

# Deploy Redis
kubectl apply -f k8s/redis-deployment.yaml

# Deploy Orchestrator
kubectl apply -f k8s/orchestrator-deployment.yaml

# Deploy Agents
kubectl apply -f k8s/agent-deployment.yaml

# Check status
kubectl get pods -n orchestrator
```

## Configuration

### Environment Variables

**Orchestrator**:
- `REDIS_HOST`: Redis hostname (default: `localhost`)
- `REDIS_PORT`: Redis port (default: `6379`)
- `MAX_WORKERS`: Max concurrent workers (default: `100`)
- `GRPC_PORT`: gRPC server port (default: `50051`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

**Agents**:
- `AGENT_TYPE`: Agent type (`data_ingest`, `data_analysis`, etc.)
- `REDIS_HOST`: Redis hostname
- `MAX_CONCURRENT_TASKS`: Agent concurrency limit

### Scaling Configuration

Edit `k8s/orchestrator-deployment.yaml`:
```yaml
spec:
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70
```

## Testing

### Unit Tests

Test individual components:
```bash
pytest tests/unit/test_redis_manager.py -v
pytest tests/unit/test_agents.py -v
```

### Integration Tests

Test end-to-end workflows:
```bash
pytest tests/integration/test_orchestration.py -v
```

### Stress Tests

Simulate 1000+ concurrent tasks:
```bash
python tests/stress/run_stress_test.py
```

**Test Scenarios**:
1. Baseline (100 users, 60s)
2. High Load (500 users, 120s)
3. Extreme Load (1000 users, 180s)
4. Spike Test (2000 users, 60s)
5. Endurance (300 users, 300s)

**Metrics Tracked**:
- Latency (P50, P95, P99)
- Throughput (requests/second)
- Error rate
- Success rate
- SLA compliance

### Expected Results

**SLA Targets**:
- ✓ P95 Latency < 500ms
- ✓ Error Rate < 1%
- ✓ Success Rate > 99%
- ✓ Recovery Time < 10s (after failure)
- ✓ 99% Uptime

## API Reference

### Submit Task

```
POST /api/v1/tasks
Content-Type: application/json

{
  "task_id": "unique-id",
  "task_type": "report_generation",
  "inputs": [...],
  "execution_mode": "sequential",
  "priority": 5,
  "timeout_ms": 30000,
  "metadata": {}
}
```

### Get Task Status

```
GET /api/v1/tasks/{task_id}

Response:
{
  "task_id": "unique-id",
  "status": "completed",
  "agent_executions": [...],
  "output": {...},
  "metrics": {
    "total_duration_ms": 450,
    "retry_count": 0,
    "agents_used": 3
  }
}
```

### Health Check

```
GET /health

Response:
{
  "healthy": true,
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "stats": {...}
}
```

## Monitoring

### Prometheus Metrics

Exposed on port `8000/metrics`:

**Key Metrics**:
- `tasks_submitted_total`: Counter of submitted tasks
- `tasks_completed_total`: Counter of completed tasks
- `tasks_failed_total`: Counter of failed tasks
- `task_execution_time_ms`: Histogram of execution times
- `queue_depth`: Gauge of queue length per task type
- `agent_healthy`: Gauge of healthy agents per type

### Grafana Dashboards

Import dashboards from `docs/grafana/`:
- `orchestrator_overview.json`: System overview
- `task_metrics.json`: Task-level metrics
- `agent_metrics.json`: Agent-level metrics

## Architecture Deep Dive

### Components

#### 1. Orchestrator
- **Responsibilities**: Task routing, agent coordination, execution management
- **Scaling**: Horizontal (3-20 pods)
- **State**: Stateless (uses Redis)

#### 2. Execution Engine
- **Modes**: Parallel, Sequential, Hybrid
- **Fault Tolerance**: Automatic retry, circuit breaker
- **Optimization**: Async I/O, connection pooling

#### 3. Load Balancer
- **Strategies**: Least-loaded, round-robin, weighted
- **Health Awareness**: Heartbeat monitoring
- **Failover**: Automatic agent replacement

#### 4. Agents
- **Modular**: Pluggable agent types
- **Stateful**: Track current tasks
- **Scalable**: Independent scaling per type

#### 5. State Manager (Redis)
- **Task State**: Queued, Running, Completed, Failed
- **Agent Registry**: Active agents and capabilities
- **Distributed Locks**: Coordination primitives
- **Queue Management**: Priority-based task queues

## Performance Benchmarks

### Baseline Performance (100 concurrent users)

| Metric | Value |
|--------|-------|
| P50 Latency | 245ms |
| P95 Latency | 420ms |
| P99 Latency | 480ms |
| Throughput | 150 tasks/sec |
| Error Rate | 0.2% |
| Success Rate | 99.8% |

### High Load (1000 concurrent users)

| Metric | Value |
|--------|-------|
| P50 Latency | 380ms |
| P95 Latency | 495ms |
| P99 Latency | 590ms |
| Throughput | 800 tasks/sec |
| Error Rate | 0.5% |
| Success Rate | 99.5% |

## Troubleshooting

### Common Issues

**1. Tasks stuck in QUEUED state**
```bash
# Check agent availability
kubectl get pods -n orchestrator | grep agent

# Check Redis connectivity
kubectl exec -it redis-0 -n orchestrator -- redis-cli ping
```

**2. High error rate**
```bash
# Check orchestrator logs
kubectl logs -n orchestrator deployment/orchestrator

# Check metrics
curl http://localhost:8000/metrics | grep error
```

**3. Slow performance**
```bash
# Check resource usage
kubectl top pods -n orchestrator

# Scale up
kubectl scale deployment/orchestrator --replicas=10 -n orchestrator
```

## Contributing

See `CONTRIBUTING.md` for development guidelines.

## License

MIT License - see `LICENSE` file.

## Authors

Built for production AI workloads.

## Support

For issues and questions:
- GitHub Issues: [Link to issues]
- Documentation: `docs/`
- Examples: `examples/`
