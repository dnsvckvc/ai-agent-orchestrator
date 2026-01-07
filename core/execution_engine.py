"""
Execution Engine - Handles parallel, sequential, and hybrid task execution
"""

import asyncio
import time
import grpc
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
import logging

from state.redis_manager import RedisStateManager, TaskState

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    HYBRID = "hybrid"


@dataclass
class AgentTaskResult:
    agent_id: str
    agent_type: str
    status: str
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time_ms: float


class ExecutionEngine:
    """
    Manages different execution strategies for agent coordination
    """

    def __init__(self, state_manager: RedisStateManager):
        self.state_manager = state_manager
        self.grpc_timeout = 30  # seconds

    async def execute_parallel(self, task_id: str, execution_plan: List[Dict[str, Any]],
                               task_state: TaskState) -> Dict[str, Any]:
        """
        Execute all agents in parallel - fastest execution
        Use case: Independent operations like parallel data processing
        """
        logger.info(f"Executing task {task_id} in PARALLEL mode with {len(execution_plan)} agents")

        start_time = time.time()

        # Create tasks for all agents
        agent_tasks = [
            self._execute_agent_task(task_id, agent_plan)
            for agent_plan in execution_plan
        ]

        # Wait for all to complete
        results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Process results
        successful_results = []
        failed_results = []

        for i, result in enumerate(results):
            agent_plan = execution_plan[i]

            if isinstance(result, Exception):
                logger.error(f"Agent {agent_plan['agent_id']} failed: {result}")
                failed_results.append({
                    "agent_id": agent_plan['agent_id'],
                    "error": str(result)
                })
            else:
                successful_results.append(result)

                # Record agent execution
                self.state_manager.add_agent_execution(task_id, {
                    "agent_id": result.agent_id,
                    "agent_type": result.agent_type,
                    "status": result.status,
                    "execution_time_ms": result.execution_time_ms,
                    "error": result.error
                })

        execution_time = (time.time() - start_time) * 1000

        # Aggregate results
        if failed_results and len(failed_results) == len(execution_plan):
            raise RuntimeError(f"All agents failed: {failed_results}")

        return {
            "execution_mode": "parallel",
            "execution_time_ms": execution_time,
            "successful_agents": len(successful_results),
            "failed_agents": len(failed_results),
            "results": [r.output for r in successful_results if r.output],
            "errors": failed_results
        }

    async def execute_sequential(self, task_id: str, execution_plan: List[Dict[str, Any]],
                                 task_state: TaskState) -> Dict[str, Any]:
        """
        Execute agents sequentially - output of one feeds into next
        Use case: Pipeline processing (data ingest -> analysis -> synthesis)
        """
        logger.info(f"Executing task {task_id} in SEQUENTIAL mode with {len(execution_plan)} agents")

        start_time = time.time()
        results = []
        pipeline_data = task_state.metadata.get("inputs", [])

        for i, agent_plan in enumerate(execution_plan):
            logger.info(f"Executing agent {i+1}/{len(execution_plan)}: {agent_plan['agent_type']}")

            # Update agent plan with output from previous step
            if results:
                agent_plan['inputs'] = results[-1].output

            try:
                result = await self._execute_agent_task(task_id, agent_plan)
                results.append(result)

                # Record agent execution
                self.state_manager.add_agent_execution(task_id, {
                    "agent_id": result.agent_id,
                    "agent_type": result.agent_type,
                    "status": result.status,
                    "execution_time_ms": result.execution_time_ms,
                    "error": result.error
                })

                if result.status == "failed":
                    logger.error(f"Agent {result.agent_id} failed, stopping pipeline")
                    break

            except Exception as e:
                logger.error(f"Agent execution failed: {e}")
                results.append(AgentTaskResult(
                    agent_id=agent_plan['agent_id'],
                    agent_type=agent_plan['agent_type'],
                    status="failed",
                    output=None,
                    error=str(e),
                    execution_time_ms=0
                ))
                break

        execution_time = (time.time() - start_time) * 1000

        # Get final output (last successful result)
        final_output = None
        for result in reversed(results):
            if result.output:
                final_output = result.output
                break

        return {
            "execution_mode": "sequential",
            "execution_time_ms": execution_time,
            "agents_executed": len(results),
            "pipeline_successful": all(r.status == "completed" for r in results),
            "final_output": final_output,
            "pipeline_results": [
                {
                    "agent_type": r.agent_type,
                    "status": r.status,
                    "execution_time_ms": r.execution_time_ms
                }
                for r in results
            ]
        }

    async def execute_hybrid(self, task_id: str, execution_plan: List[Dict[str, Any]],
                            task_state: TaskState) -> Dict[str, Any]:
        """
        Execute agents in hybrid mode - some parallel, some sequential
        Use case: Complex workflows with both parallel and sequential dependencies
        """
        logger.info(f"Executing task {task_id} in HYBRID mode")

        # Group agents by dependency stage
        # Stage 0: Can run in parallel (no dependencies)
        # Stage 1: Depends on Stage 0 (sequential after parallel)
        # etc.

        # For this implementation, we'll do a simple 2-stage approach:
        # 1. Run first half in parallel
        # 2. Run second half sequentially using first half's output

        start_time = time.time()
        mid_point = len(execution_plan) // 2 if len(execution_plan) > 1 else 1

        stage1_plan = execution_plan[:mid_point]
        stage2_plan = execution_plan[mid_point:]

        # Stage 1: Parallel execution
        logger.info(f"Hybrid Stage 1: Executing {len(stage1_plan)} agents in parallel")
        stage1_results = await self.execute_parallel(task_id, stage1_plan, task_state)

        # Stage 2: Sequential execution with Stage 1 output
        if stage2_plan:
            logger.info(f"Hybrid Stage 2: Executing {len(stage2_plan)} agents sequentially")

            # Update task state with Stage 1 results
            task_state.metadata['inputs'] = stage1_results.get('results', [])

            stage2_results = await self.execute_sequential(task_id, stage2_plan, task_state)
        else:
            stage2_results = {"final_output": stage1_results}

        execution_time = (time.time() - start_time) * 1000

        return {
            "execution_mode": "hybrid",
            "execution_time_ms": execution_time,
            "stage1_results": stage1_results,
            "stage2_results": stage2_results,
            "final_output": stage2_results.get('final_output')
        }

    async def _execute_agent_task(self, task_id: str,
                                  agent_plan: Dict[str, Any]) -> AgentTaskResult:
        """
        Execute a single agent task via gRPC
        """
        agent_id = agent_plan['agent_id']
        agent_type = agent_plan['agent_type']
        endpoint = agent_plan['endpoint']

        start_time = time.time()

        try:
            # Increment agent task count
            self.state_manager.increment_agent_tasks(agent_id, 1)

            # Simulate gRPC call (in production, this would be actual gRPC)
            # For now, we'll call the agent directly
            output = await self._call_agent_grpc(
                endpoint,
                task_id,
                agent_type,
                agent_plan.get('inputs', []),
                agent_plan.get('parameters', {})
            )

            execution_time = (time.time() - start_time) * 1000

            # Decrement agent task count
            self.state_manager.increment_agent_tasks(agent_id, -1)

            return AgentTaskResult(
                agent_id=agent_id,
                agent_type=agent_type,
                status="completed",
                output=output,
                error=None,
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Agent {agent_id} execution failed: {e}")

            # Decrement agent task count
            self.state_manager.increment_agent_tasks(agent_id, -1)

            return AgentTaskResult(
                agent_id=agent_id,
                agent_type=agent_type,
                status="failed",
                output=None,
                error=str(e),
                execution_time_ms=execution_time
            )

    async def _call_agent_grpc(self, endpoint: str, task_id: str, agent_type: str,
                              inputs: List[Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make gRPC call to agent service
        In production, this uses the generated gRPC client
        """
        # This is a placeholder for actual gRPC implementation
        # In production, you would:
        # 1. Create gRPC channel
        # 2. Create stub
        # 3. Make RPC call
        # 4. Handle response

        try:
            # Simulate agent processing
            await asyncio.sleep(0.1)  # Simulate network latency

            # For demo, return mock data based on agent type
            if agent_type == "data_ingest":
                return {
                    "type": "ingested_data",
                    "data": {"records": 1000, "format": "json"},
                    "metadata": {"source": "uploaded_files"}
                }
            elif agent_type == "data_analysis":
                return {
                    "type": "analysis_result",
                    "data": {
                        "summary_stats": {"mean": 42.5, "median": 40.0},
                        "insights": ["Trend increasing", "Outliers detected"]
                    }
                }
            elif agent_type == "synthesis":
                return {
                    "type": "json_report",
                    "data": {
                        "title": "Data Analysis Report",
                        "summary": "Analysis completed successfully",
                        "findings": ["Finding 1", "Finding 2"],
                        "recommendations": ["Recommendation 1"]
                    }
                }
            elif agent_type == "video_detection":
                return {
                    "type": "detections",
                    "data": {
                        "objects_detected": ["person", "vehicle"],
                        "confidence": 0.95,
                        "timestamp": time.time()
                    }
                }
            elif agent_type == "alerting":
                return {
                    "type": "alert",
                    "data": {
                        "alert_id": f"alert_{task_id}",
                        "severity": "high",
                        "message": "Anomaly detected",
                        "timestamp": time.time()
                    }
                }
            else:
                return {"type": "generic", "data": {"status": "completed"}}

        except grpc.RpcError as e:
            logger.error(f"gRPC error calling {endpoint}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling agent {endpoint}: {e}")
            raise
