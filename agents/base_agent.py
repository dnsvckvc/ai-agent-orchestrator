"""
Base Agent class - Foundation for all modular agents
Provides common functionality: health checks, error handling, metrics
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


@dataclass
class AgentInput:
    """Input data for agent processing"""
    input_id: str
    input_type: str  # text, image, video, json, etc.
    data: Any
    metadata: Dict[str, Any]


@dataclass
class AgentOutput:
    """Output from agent processing"""
    output_type: str
    data: Any
    metadata: Dict[str, Any]
    processing_time_ms: float


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    Implements common patterns: initialization, health checks, error handling
    """

    def __init__(self, agent_id: str, agent_type: str, max_concurrent_tasks: int = 10):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.agent_type = agent_type
        self.max_concurrent_tasks = max_concurrent_tasks

        self.current_tasks = 0
        self.total_completed = 0
        self.total_failed = 0
        self.healthy = True
        self.start_time = time.time()

        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)

        logger.info(f"Agent {self.agent_id} ({self.agent_type}) initialized")

    @abstractmethod
    async def process(self, inputs: List[AgentInput], parameters: Dict[str, Any]) -> AgentOutput:
        """
        Main processing method - must be implemented by subclasses
        """
        pass

    async def execute(self, task_id: str, inputs: List[AgentInput],
                     parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent task with error handling and metrics
        """
        start_time = time.time()

        async with self._task_semaphore:
            self.current_tasks += 1

            try:
                logger.info(f"Agent {self.agent_id} executing task {task_id}")

                # Validate inputs
                self._validate_inputs(inputs)

                # Process
                output = await self.process(inputs, parameters)

                # Success
                self.total_completed += 1
                processing_time = (time.time() - start_time) * 1000

                logger.info(
                    f"Agent {self.agent_id} completed task {task_id} in {processing_time:.2f}ms"
                )

                return {
                    "status": "completed",
                    "output": {
                        "type": output.output_type,
                        "data": output.data,
                        "metadata": output.metadata
                    },
                    "execution_time_ms": processing_time,
                    "error": None
                }

            except Exception as e:
                self.total_failed += 1
                processing_time = (time.time() - start_time) * 1000

                logger.error(f"Agent {self.agent_id} failed task {task_id}: {e}")

                return {
                    "status": "failed",
                    "output": None,
                    "execution_time_ms": processing_time,
                    "error": {
                        "message": str(e),
                        "type": type(e).__name__
                    }
                }

            finally:
                self.current_tasks -= 1

    def _validate_inputs(self, inputs: List[AgentInput]):
        """Validate inputs before processing"""
        if not inputs:
            raise ValueError("No inputs provided")

        for inp in inputs:
            if not inp.input_type:
                raise ValueError("Input type is required")
            if inp.data is None:
                raise ValueError("Input data is required")

    def get_health(self) -> Dict[str, Any]:
        """Get agent health status"""
        uptime = time.time() - self.start_time

        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "healthy": self.healthy,
            "current_tasks": self.current_tasks,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "uptime_seconds": uptime,
            "success_rate": (
                self.total_completed / (self.total_completed + self.total_failed)
                if (self.total_completed + self.total_failed) > 0 else 1.0
            )
        }

    def get_capabilities(self) -> List[str]:
        """Get agent capabilities"""
        return [self.agent_type]

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info(f"Agent {self.agent_id} shutting down...")
        self.healthy = False

        # Wait for current tasks to complete
        while self.current_tasks > 0:
            await asyncio.sleep(0.1)

        logger.info(f"Agent {self.agent_id} shutdown complete")
