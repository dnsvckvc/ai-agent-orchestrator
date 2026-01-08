"""
Core Orchestrator - Manages task distribution, agent coordination, and execution
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging

from state.redis_manager import RedisStateManager, TaskState, TaskStatus, AgentInfo
from core.execution_engine import ExecutionEngine, ExecutionMode
from core.load_balancer import LoadBalancer
from monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class TaskDefinition:
    task_id: str
    task_type: str
    inputs: List[Dict[str, Any]]
    execution_mode: ExecutionMode
    priority: int
    timeout_ms: int
    metadata: Dict[str, Any]


class Orchestrator:
    """
    Main orchestrator that coordinates task execution across distributed agents
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379,
                 max_workers: int = 100):
        self.state_manager = RedisStateManager(redis_host, redis_port)
        self.execution_engine = ExecutionEngine(self.state_manager)
        self.load_balancer = LoadBalancer(self.state_manager)
        self.metrics = MetricsCollector()

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.task_processors: Dict[str, asyncio.Task] = {}

        # Task type to agent type mapping
        self.task_agent_mapping = {
            # Original workflows (placeholder agents)
            "report_generation": ["data_ingest", "data_analysis", "synthesis"],
            "real_time_monitoring": ["video_detection", "alerting"],
            "data_analysis": ["data_analysis"],
            "api_call": ["api_caller"],

            # New production workflows
            "podcast_intelligence": [
                "rss_feed_monitor",
                "podcast_transcript",
                "transcript_summary",
                "industry_synthesis"
            ],
            "document_intelligence": [
                "document_reader",
                "transcript_summary",
                "industry_synthesis"
            ],
            "content_summarization": [
                "transcript_summary"
            ],
            "industry_synthesis_only": [
                "industry_synthesis"
            ],
        }

    async def start(self):
        """Start the orchestrator"""
        logger.info("Starting orchestrator...")
        self.running = True

        # Start background tasks
        asyncio.create_task(self._process_task_queues())
        asyncio.create_task(self._monitor_health())
        asyncio.create_task(self._cleanup_stale_agents())

        logger.info("Orchestrator started successfully")

    async def stop(self):
        """Stop the orchestrator"""
        logger.info("Stopping orchestrator...")
        self.running = False

        # Cancel all running task processors
        for task in self.task_processors.values():
            task.cancel()

        self.executor.shutdown(wait=True)
        logger.info("Orchestrator stopped")

    async def submit_task(self, task_def: TaskDefinition) -> Dict[str, Any]:
        """
        Submit a new task for orchestration
        Returns task response with ID and initial status
        """
        start_time = time.time()

        try:
            # Create task state
            task_state = TaskState(
                task_id=task_def.task_id,
                status=TaskStatus.QUEUED,
                task_type=task_def.task_type,
                created_at=start_time,
                updated_at=start_time,
                agent_executions=[],
                metadata=task_def.metadata,
                priority=task_def.priority
            )

            # Save to Redis
            success = self.state_manager.create_task(task_state)

            if not success:
                return {
                    "task_id": task_def.task_id,
                    "status": "failed",
                    "message": "Failed to create task",
                    "error": "State management error"
                }

            # Record metrics
            self.metrics.increment("tasks_submitted")
            self.metrics.increment(f"tasks_submitted_{task_def.task_type}")

            logger.info(f"Task {task_def.task_id} submitted successfully")

            return {
                "task_id": task_def.task_id,
                "status": "queued",
                "message": "Task submitted successfully",
                "estimated_completion_ms": self._estimate_completion_time(task_def)
            }

        except Exception as e:
            logger.error(f"Failed to submit task {task_def.task_id}: {e}")
            self.metrics.increment("tasks_submit_failed")
            return {
                "task_id": task_def.task_id,
                "status": "failed",
                "message": str(e),
                "error": "Submission error"
            }

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a task"""
        try:
            task_state = self.state_manager.get_task(task_id)

            if not task_state:
                return None

            # Calculate metrics
            total_duration = (task_state.updated_at - task_state.created_at) * 1000

            return {
                "task_id": task_id,
                "status": task_state.status.value,
                "agent_executions": task_state.agent_executions,
                "output": task_state.output,
                "error": task_state.error,
                "metrics": {
                    "total_duration_ms": total_duration,
                    "retry_count": task_state.retry_count,
                    "agents_used": len(task_state.agent_executions)
                }
            }

        except Exception as e:
            logger.error(f"Failed to get task status {task_id}: {e}")
            return None

    async def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """Cancel a running task"""
        try:
            task_state = self.state_manager.get_task(task_id)

            if not task_state:
                logger.warning(f"Task {task_id} not found for cancellation")
                return False

            if task_state.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                logger.warning(f"Task {task_id} already in terminal state: {task_state.status.value}")
                return False

            # Update status to cancelled
            success = self.state_manager.update_task_status(
                task_id,
                TaskStatus.CANCELLED,
                error={"message": f"Cancelled: {reason}", "code": "CANCELLED"}
            )

            if success:
                self.metrics.increment("tasks_cancelled")
                logger.info(f"Task {task_id} cancelled: {reason}")

            return success

        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False

    async def _process_task_queues(self):
        """Background task to process queued tasks"""
        logger.info("Task queue processor started")

        while self.running:
            try:
                # Process each task type
                for task_type in self.task_agent_mapping.keys():
                    queue_length = self.state_manager.get_queue_length(task_type)

                    if queue_length > 0:
                        task_id = self.state_manager.get_next_task(task_type)

                        if task_id:
                            # Process task asynchronously
                            task = asyncio.create_task(self._execute_task(task_id))
                            self.task_processors[task_id] = task

                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in task queue processor: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, task_id: str):
        """Execute a task by coordinating agents"""
        start_time = time.time()
        task_state = self.state_manager.get_task(task_id)

        if not task_state:
            logger.error(f"Task {task_id} not found")
            return

        try:
            # Update status to running
            self.state_manager.update_task_status(task_id, TaskStatus.RUNNING)
            self.metrics.increment("tasks_running")

            # Get required agent types
            required_agents = self.task_agent_mapping.get(task_state.task_type, [])

            if not required_agents:
                raise ValueError(f"Unknown task type: {task_state.task_type}")

            # Build execution plan
            execution_plan = self._build_execution_plan(task_state, required_agents)

            # Execute based on execution mode
            execution_mode = task_state.metadata.get("execution_mode", "sequential")

            if execution_mode == "parallel":
                result = await self.execution_engine.execute_parallel(
                    task_id, execution_plan, task_state
                )
            elif execution_mode == "sequential":
                result = await self.execution_engine.execute_sequential(
                    task_id, execution_plan, task_state
                )
            else:  # hybrid
                result = await self.execution_engine.execute_hybrid(
                    task_id, execution_plan, task_state
                )

            # Update task with result
            execution_time = (time.time() - start_time) * 1000

            self.state_manager.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                output=result
            )

            # Record metrics
            self.metrics.increment("tasks_completed")
            self.metrics.record("task_execution_time_ms", execution_time)

            if execution_time < 500:
                self.metrics.increment("tasks_under_500ms")

            logger.info(f"Task {task_id} completed in {execution_time:.2f}ms")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")

            # Check if retryable
            if task_state.retry_count < 3:
                # Retry with exponential backoff
                task_state.retry_count += 1
                self.state_manager.update_task_status(task_id, TaskStatus.RETRYING)

                await asyncio.sleep(2 ** task_state.retry_count)

                # Re-queue task
                self.state_manager.create_task(task_state)
                self.metrics.increment("tasks_retried")
            else:
                # Mark as failed
                self.state_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error={
                        "message": str(e),
                        "code": "EXECUTION_FAILED",
                        "retryable": False
                    }
                )
                self.metrics.increment("tasks_failed")

        finally:
            # Cleanup
            if task_id in self.task_processors:
                del self.task_processors[task_id]

    def _build_execution_plan(self, task_state: TaskState,
                             required_agents: List[str]) -> List[Dict[str, Any]]:
        """Build execution plan for agents"""
        plan = []

        for agent_type in required_agents:
            # Get available agents using load balancer
            agent = self.load_balancer.select_agent(agent_type)

            if not agent:
                raise RuntimeError(f"No available agents for type: {agent_type}")

            plan.append({
                "agent_id": agent.agent_id,
                "agent_type": agent_type,
                "endpoint": agent.endpoint,
                "inputs": task_state.metadata.get("inputs", []),
                "parameters": task_state.metadata.get("parameters", {})
            })

        return plan

    def _estimate_completion_time(self, task_def: TaskDefinition) -> int:
        """Estimate task completion time based on historical data"""
        # Simple estimation - in production, use ML model
        base_time = 1000  # 1 second base

        # Adjust based on task type
        type_multipliers = {
            "report_generation": 3.0,
            "real_time_monitoring": 0.5,
            "data_analysis": 2.0,
            "api_call": 0.3
        }

        multiplier = type_multipliers.get(task_def.task_type, 1.0)
        return int(base_time * multiplier)

    async def _monitor_health(self):
        """Monitor system health"""
        while self.running:
            try:
                # Check Redis health
                redis_healthy = self.state_manager.health_check()

                if not redis_healthy:
                    logger.error("Redis health check failed!")
                    self.metrics.increment("health_check_failed_redis")

                # Monitor queue depths
                for task_type in self.task_agent_mapping.keys():
                    queue_length = self.state_manager.get_queue_length(task_type)
                    self.metrics.record(f"queue_depth_{task_type}", queue_length)

                    if queue_length > 100:
                        logger.warning(f"High queue depth for {task_type}: {queue_length}")

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(10)

    async def _cleanup_stale_agents(self):
        """Cleanup stale agents periodically"""
        while self.running:
            try:
                self.state_manager.cleanup_stale_agents(max_age_seconds=60)
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Agent cleanup error: {e}")
                await asyncio.sleep(30)

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            "running": self.running,
            "active_tasks": len(self.task_processors),
            "max_workers": self.max_workers,
            "metrics": self.metrics.get_all_metrics()
        }
