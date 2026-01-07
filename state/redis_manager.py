"""
Redis State Manager for distributed task orchestration
Handles task state, agent registry, and distributed locking
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from redis.client import Redis
from redis.exceptions import LockError
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class TaskState:
    task_id: str
    status: TaskStatus
    task_type: str
    created_at: float
    updated_at: float
    agent_executions: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    priority: int = 5


@dataclass
class AgentInfo:
    agent_id: str
    agent_type: str
    endpoint: str
    capabilities: List[str]
    max_concurrent_tasks: int
    current_tasks: int
    healthy: bool
    last_heartbeat: float
    metadata: Dict[str, Any]


class RedisStateManager:
    """Manages distributed state using Redis"""

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379,
                 redis_db: int = 0, redis_password: Optional[str] = None):
        self.redis_client: Redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )

        # Key prefixes
        self.TASK_PREFIX = "task:"
        self.AGENT_PREFIX = "agent:"
        self.QUEUE_PREFIX = "queue:"
        self.LOCK_PREFIX = "lock:"
        self.METRICS_PREFIX = "metrics:"

        self._ensure_connection()

    def _ensure_connection(self):
        """Ensure Redis connection is healthy"""
        try:
            self.redis_client.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    # Task State Management

    def create_task(self, task_state: TaskState) -> bool:
        """Create a new task in Redis"""
        try:
            task_key = f"{self.TASK_PREFIX}{task_state.task_id}"
            task_data = asdict(task_state)
            task_data['status'] = task_state.status.value

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.set(task_key, json.dumps(task_data))
            pipe.zadd(
                f"{self.QUEUE_PREFIX}{task_state.task_type}",
                {task_state.task_id: task_state.priority}
            )
            pipe.execute()

            logger.info(f"Task {task_state.task_id} created with status {task_state.status.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to create task {task_state.task_id}: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[TaskState]:
        """Get task state from Redis"""
        try:
            task_key = f"{self.TASK_PREFIX}{task_id}"
            task_data = self.redis_client.get(task_key)

            if not task_data:
                return None

            data = json.loads(task_data)
            data['status'] = TaskStatus(data['status'])
            return TaskState(**data)
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None

    def update_task_status(self, task_id: str, status: TaskStatus,
                          error: Optional[Dict] = None,
                          output: Optional[Dict] = None) -> bool:
        """Update task status atomically"""
        try:
            task_key = f"{self.TASK_PREFIX}{task_id}"
            task = self.get_task(task_id)

            if not task:
                logger.warning(f"Task {task_id} not found")
                return False

            task.status = status
            task.updated_at = time.time()

            if error:
                task.error = error
            if output:
                task.output = output

            task_data = asdict(task)
            task_data['status'] = status.value

            self.redis_client.set(task_key, json.dumps(task_data))

            # Publish update to subscribers
            self.redis_client.publish(
                f"task_updates:{task_id}",
                json.dumps({"status": status.value, "timestamp": time.time()})
            )

            logger.info(f"Task {task_id} status updated to {status.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            return False

    def add_agent_execution(self, task_id: str, agent_execution: Dict[str, Any]) -> bool:
        """Add agent execution info to task"""
        try:
            task = self.get_task(task_id)
            if not task:
                return False

            task.agent_executions.append(agent_execution)
            task.updated_at = time.time()

            task_key = f"{self.TASK_PREFIX}{task_id}"
            task_data = asdict(task)
            task_data['status'] = task.status.value

            self.redis_client.set(task_key, json.dumps(task_data))
            return True
        except Exception as e:
            logger.error(f"Failed to add agent execution for task {task_id}: {e}")
            return False

    # Queue Management

    def get_next_task(self, task_type: str) -> Optional[str]:
        """Get next task from priority queue (highest priority first)"""
        try:
            queue_key = f"{self.QUEUE_PREFIX}{task_type}"
            # Get highest priority task (lowest score)
            result = self.redis_client.zpopmin(queue_key, 1)

            if result:
                task_id, _ = result[0]
                return task_id
            return None
        except Exception as e:
            logger.error(f"Failed to get next task from queue {task_type}: {e}")
            return None

    def get_queue_length(self, task_type: str) -> int:
        """Get number of tasks in queue"""
        try:
            queue_key = f"{self.QUEUE_PREFIX}{task_type}"
            return self.redis_client.zcard(queue_key)
        except Exception as e:
            logger.error(f"Failed to get queue length for {task_type}: {e}")
            return 0

    # Agent Registry

    def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register an agent"""
        try:
            agent_key = f"{self.AGENT_PREFIX}{agent_info.agent_id}"
            agent_data = asdict(agent_info)

            self.redis_client.set(agent_key, json.dumps(agent_data))

            # Add to agent type index
            self.redis_client.sadd(
                f"{self.AGENT_PREFIX}type:{agent_info.agent_type}",
                agent_info.agent_id
            )

            logger.info(f"Agent {agent_info.agent_id} registered")
            return True
        except Exception as e:
            logger.error(f"Failed to register agent {agent_info.agent_id}: {e}")
            return False

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information"""
        try:
            agent_key = f"{self.AGENT_PREFIX}{agent_id}"
            agent_data = self.redis_client.get(agent_key)

            if not agent_data:
                return None

            return AgentInfo(**json.loads(agent_data))
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            return None

    def get_agents_by_type(self, agent_type: str) -> List[AgentInfo]:
        """Get all agents of a specific type"""
        try:
            agent_ids = self.redis_client.smembers(
                f"{self.AGENT_PREFIX}type:{agent_type}"
            )

            agents = []
            for agent_id in agent_ids:
                agent = self.get_agent(agent_id)
                if agent and agent.healthy:
                    agents.append(agent)

            return agents
        except Exception as e:
            logger.error(f"Failed to get agents by type {agent_type}: {e}")
            return []

    def update_agent_heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat timestamp"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return False

            agent.last_heartbeat = time.time()
            agent_key = f"{self.AGENT_PREFIX}{agent_id}"
            self.redis_client.set(agent_key, json.dumps(asdict(agent)))
            return True
        except Exception as e:
            logger.error(f"Failed to update heartbeat for agent {agent_id}: {e}")
            return False

    def increment_agent_tasks(self, agent_id: str, increment: int = 1) -> bool:
        """Increment/decrement agent current task count"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return False

            agent.current_tasks = max(0, agent.current_tasks + increment)
            agent_key = f"{self.AGENT_PREFIX}{agent_id}"
            self.redis_client.set(agent_key, json.dumps(asdict(agent)))
            return True
        except Exception as e:
            logger.error(f"Failed to update task count for agent {agent_id}: {e}")
            return False

    # Distributed Locking

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> Optional[redis.lock.Lock]:
        """Acquire a distributed lock"""
        try:
            lock_key = f"{self.LOCK_PREFIX}{lock_name}"
            lock = self.redis_client.lock(lock_key, timeout=timeout)

            if lock.acquire(blocking=True, blocking_timeout=timeout):
                return lock
            return None
        except Exception as e:
            logger.error(f"Failed to acquire lock {lock_name}: {e}")
            return None

    def release_lock(self, lock: redis.lock.Lock) -> bool:
        """Release a distributed lock"""
        try:
            lock.release()
            return True
        except LockError as e:
            logger.error(f"Failed to release lock: {e}")
            return False

    # Metrics

    def increment_metric(self, metric_name: str, value: int = 1):
        """Increment a metric counter"""
        try:
            metric_key = f"{self.METRICS_PREFIX}{metric_name}"
            self.redis_client.incrby(metric_key, value)
        except Exception as e:
            logger.error(f"Failed to increment metric {metric_name}: {e}")

    def set_metric(self, metric_name: str, value: float):
        """Set a metric value"""
        try:
            metric_key = f"{self.METRICS_PREFIX}{metric_name}"
            self.redis_client.set(metric_key, value)
        except Exception as e:
            logger.error(f"Failed to set metric {metric_name}: {e}")

    def get_metric(self, metric_name: str) -> Optional[float]:
        """Get a metric value"""
        try:
            metric_key = f"{self.METRICS_PREFIX}{metric_name}"
            value = self.redis_client.get(metric_key)
            return float(value) if value else None
        except Exception as e:
            logger.error(f"Failed to get metric {metric_name}: {e}")
            return None

    # Pub/Sub for task updates

    def subscribe_to_task_updates(self, task_id: str):
        """Subscribe to task updates"""
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(f"task_updates:{task_id}")
        return pubsub

    # Cleanup

    def cleanup_stale_agents(self, max_age_seconds: int = 60):
        """Remove stale agents that haven't sent heartbeat"""
        try:
            current_time = time.time()
            agent_pattern = f"{self.AGENT_PREFIX}*"

            for key in self.redis_client.scan_iter(match=agent_pattern, count=100):
                if key.startswith(f"{self.AGENT_PREFIX}type:"):
                    continue

                agent_data = self.redis_client.get(key)
                if agent_data:
                    agent = AgentInfo(**json.loads(agent_data))
                    if current_time - agent.last_heartbeat > max_age_seconds:
                        # Remove stale agent
                        self.redis_client.delete(key)
                        self.redis_client.srem(
                            f"{self.AGENT_PREFIX}type:{agent.agent_type}",
                            agent.agent_id
                        )
                        logger.warning(f"Removed stale agent {agent.agent_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup stale agents: {e}")

    def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            return self.redis_client.ping()
        except Exception:
            return False
