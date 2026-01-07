"""
Example: Real-Time Monitoring Use Case
Demonstrates video monitoring with alerting
"""

import asyncio
import time
from core.orchestrator import Orchestrator, TaskDefinition
from core.execution_engine import ExecutionMode
from state.redis_manager import RedisStateManager, AgentInfo
from agents.video_detection_agent import VideoDetectionAgent
from agents.alerting_agent import AlertingAgent


async def setup_monitoring_agents(state_manager):
    """Register monitoring agents"""
    print("Setting up monitoring agents...")

    agents = [
        VideoDetectionAgent(agent_id="video-det-1", max_concurrent_tasks=10),
        AlertingAgent(agent_id="alerting-1", max_concurrent_tasks=20)
    ]

    for agent in agents:
        agent_info = AgentInfo(
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            endpoint=f"localhost:5006{agents.index(agent)}",
            capabilities=agent.get_capabilities(),
            max_concurrent_tasks=agent.max_concurrent_tasks,
            current_tasks=0,
            healthy=True,
            last_heartbeat=time.time(),
            metadata={"version": "1.0.0"}
        )
        state_manager.register_agent(agent_info)

    print(f"Registered {len(agents)} monitoring agents")
    return agents


async def main():
    """
    Main example: Real-Time Monitoring
    """
    print("\n" + "="*80)
    print("REAL-TIME MONITORING EXAMPLE")
    print("="*80 + "\n")

    # Create orchestrator
    orchestrator = Orchestrator(redis_host="localhost", redis_port=6379)
    await orchestrator.start()

    # Setup agents
    agents = await setup_monitoring_agents(orchestrator.state_manager)

    print("\n--- Submitting Monitoring Task ---\n")

    # Simulate video stream monitoring
    task_def = TaskDefinition(
        task_id="monitor-example-001",
        task_type="real_time_monitoring",
        inputs=[
            {
                "input_id": "camera-feed-1",
                "type": "video",
                "data": b"simulated_video_stream_data",
                "metadata": {
                    "camera_id": "CAM-001",
                    "location": "Main Entrance",
                    "fps": 30,
                    "resolution": "1920x1080"
                }
            }
        ],
        execution_mode=ExecutionMode.SEQUENTIAL,
        priority=8,  # High priority for monitoring
        timeout_ms=10000,
        metadata={
            "max_persons": 10,  # Alert if more than 10 people
            "restricted_area": True,  # This is a restricted area
            "alert_threshold": "high"
        }
    )

    # Submit task
    response = await orchestrator.submit_task(task_def)

    print(f"Task ID: {response['task_id']}")
    print(f"Status: {response['status']}")
    print(f"Priority: {task_def.priority} (High)")
    print(f"Monitoring Location: Main Entrance")

    # Monitor task progress
    print("\n--- Monitoring Progress ---\n")

    max_wait = 15  # seconds
    start_wait = time.time()
    final_status = None

    while time.time() - start_wait < max_wait:
        status = await orchestrator.get_task_status(task_def.task_id)

        if status:
            current_status = status["status"]
            elapsed = int(time.time() - start_wait)
            print(f"[{elapsed}s] Status: {current_status}")

            if current_status in ["completed", "failed", "cancelled"]:
                final_status = status
                break

        await asyncio.sleep(1)

    # Display results
    if final_status:
        print("\n--- Monitoring Results ---\n")
        print(f"Final Status: {final_status['status']}")

        if final_status.get("output"):
            output = final_status["output"]
            print("\n--- Alerts Generated ---\n")

            if output.get("data", {}).get("alerts"):
                alerts = output["data"]["alerts"]
                print(f"Total Alerts: {len(alerts)}")

                for i, alert in enumerate(alerts, 1):
                    print(f"\nAlert #{i}:")
                    print(f"  Type: {alert.get('type', 'unknown')}")
                    print(f"  Severity: {alert.get('severity', 'unknown').upper()}")
                    print(f"  Message: {alert.get('message', 'N/A')}")
                    print(f"  Requires Action: {alert.get('metadata', {}).get('requires_action', False)}")
            else:
                print("No alerts generated - all clear!")

        if final_status.get("metrics"):
            print("\n--- Performance Metrics ---\n")
            metrics = final_status["metrics"]
            print(f"Detection Latency: {metrics.get('total_duration_ms', 0):.2f}ms")
            print(f"Agents Used: {metrics.get('agents_used', 0)}")

    else:
        print("\n--- Task Timeout ---\n")
        print("Monitoring task did not complete within timeout")

    # Cleanup
    await orchestrator.stop()

    print("\n" + "="*80)
    print("MONITORING EXAMPLE COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
