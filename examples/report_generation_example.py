"""
Example: Report Generation Use Case
Demonstrates end-to-end report generation workflow
"""

import asyncio
import base64
import time
from core.orchestrator import Orchestrator, TaskDefinition
from core.execution_engine import ExecutionMode
from state.redis_manager import RedisStateManager, AgentInfo
from agents.data_ingest_agent import DataIngestAgent
from agents.data_analysis_agent import DataAnalysisAgent
from agents.synthesis_agent import SynthesisAgent


async def setup_agents(state_manager):
    """Register agents with the orchestrator"""
    print("Setting up agents...")

    # Create and register agents
    agents = [
        DataIngestAgent(agent_id="ingest-1", max_concurrent_tasks=20),
        DataAnalysisAgent(agent_id="analysis-1", max_concurrent_tasks=15),
        SynthesisAgent(agent_id="synthesis-1", max_concurrent_tasks=15)
    ]

    for agent in agents:
        agent_info = AgentInfo(
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            endpoint=f"localhost:5005{agents.index(agent)}",
            capabilities=agent.get_capabilities(),
            max_concurrent_tasks=agent.max_concurrent_tasks,
            current_tasks=0,
            healthy=True,
            last_heartbeat=time.time(),
            metadata={"version": "1.0.0"}
        )
        state_manager.register_agent(agent_info)

    print(f"Registered {len(agents)} agents")
    return agents


async def main():
    """
    Main example: Report Generation
    """
    print("\n" + "="*80)
    print("REPORT GENERATION EXAMPLE")
    print("="*80 + "\n")

    # Create orchestrator
    orchestrator = Orchestrator(redis_host="localhost", redis_port=6379)
    await orchestrator.start()

    # Setup agents
    agents = await setup_agents(orchestrator.state_manager)

    print("\n--- Submitting Report Generation Task ---\n")

    # Create task definition
    task_def = TaskDefinition(
        task_id="report-example-001",
        task_type="report_generation",
        inputs=[
            {
                "input_id": "sales-data",
                "type": "text",
                "data": "Q4 2024 Sales Data: Revenue increased by 25% compared to Q3. "
                       "Top performing products include Product A (40% growth) and Product B (30% growth). "
                       "Customer acquisition cost decreased by 15%.",
                "metadata": {"source": "sales_db"}
            },
            {
                "input_id": "chart-1",
                "type": "image",
                "data": base64.b64encode(b"fake_chart_image_data").decode(),
                "metadata": {"chart_type": "revenue_trend"}
            },
            {
                "input_id": "metrics",
                "type": "json",
                "data": {
                    "revenue": 1250000,
                    "customers": 5000,
                    "churn_rate": 0.05,
                    "nps_score": 72
                },
                "metadata": {"period": "Q4_2024"}
            }
        ],
        execution_mode=ExecutionMode.SEQUENTIAL,
        priority=5,
        timeout_ms=30000,
        metadata={
            "report_title": "Q4 2024 Sales Performance Report",
            "report_type": "quarterly_sales",
            "user_id": "analyst-123"
        }
    )

    # Submit task
    response = await orchestrator.submit_task(task_def)

    print(f"Task ID: {response['task_id']}")
    print(f"Status: {response['status']}")
    print(f"Message: {response['message']}")
    print(f"Estimated Completion: {response.get('estimated_completion_ms', 0)}ms")

    # Wait for task to complete
    print("\n--- Waiting for Task Completion ---\n")

    max_wait = 30  # seconds
    start_wait = time.time()
    final_status = None

    while time.time() - start_wait < max_wait:
        status = await orchestrator.get_task_status(task_def.task_id)

        if status:
            current_status = status["status"]
            print(f"[{int(time.time() - start_wait)}s] Status: {current_status}")

            if current_status in ["completed", "failed", "cancelled"]:
                final_status = status
                break

        await asyncio.sleep(2)

    # Display results
    if final_status:
        print("\n--- Task Completed ---\n")
        print(f"Final Status: {final_status['status']}")

        if final_status.get("output"):
            print("\n--- Report Output ---\n")
            import json
            print(json.dumps(final_status["output"], indent=2))

        if final_status.get("metrics"):
            print("\n--- Execution Metrics ---\n")
            metrics = final_status["metrics"]
            print(f"Total Duration: {metrics.get('total_duration_ms', 0):.2f}ms")
            print(f"Agents Used: {metrics.get('agents_used', 0)}")
            print(f"Retry Count: {metrics.get('retry_count', 0)}")

        if final_status.get("agent_executions"):
            print("\n--- Agent Executions ---\n")
            for exec_info in final_status["agent_executions"]:
                print(f"  Agent: {exec_info.get('agent_type', 'unknown')}")
                print(f"    Status: {exec_info.get('status', 'unknown')}")
                print(f"    Execution Time: {exec_info.get('execution_time_ms', 0):.2f}ms")
                print()

    else:
        print("\n--- Task Timeout ---\n")
        print("Task did not complete within timeout period")

    # Cleanup
    await orchestrator.stop()

    print("\n" + "="*80)
    print("EXAMPLE COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
