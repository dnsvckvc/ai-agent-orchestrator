"""
Main entry point for Agent service
Agents register with Redis and execute tasks assigned by orchestrator
"""

import asyncio
import os
import signal
import time
import logging
import uuid

from state.redis_manager import RedisStateManager, AgentInfo
from agents.data_ingest_agent import DataIngestAgent
from agents.data_analysis_agent import DataAnalysisAgent
from agents.synthesis_agent import SynthesisAgent
from agents.video_detection_agent import VideoDetectionAgent
from agents.alerting_agent import AlertingAgent
from agents.api_caller_agent import APICallerAgent

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Agent type mapping
AGENT_CLASSES = {
    "data_ingest": DataIngestAgent,
    "data_analysis": DataAnalysisAgent,
    "synthesis": SynthesisAgent,
    "video_detection": VideoDetectionAgent,
    "alerting": AlertingAgent,
    "api_caller": APICallerAgent
}


async def main():
    """Main agent service"""

    # Configuration from environment
    agent_type = os.getenv("AGENT_TYPE")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    max_concurrent = int(os.getenv("MAX_CONCURRENT_TASKS", "10"))
    agent_id = os.getenv("AGENT_ID", f"agent-{agent_type}-{uuid.uuid4().hex[:8]}")

    if not agent_type:
        logger.error("AGENT_TYPE environment variable is required")
        return

    if agent_type not in AGENT_CLASSES:
        logger.error(f"Unknown agent type: {agent_type}")
        logger.error(f"Available types: {list(AGENT_CLASSES.keys())}")
        return

    logger.info(f"Starting {agent_type} agent...")
    logger.info(f"Agent ID: {agent_id}")
    logger.info(f"Redis: {redis_host}:{redis_port}")
    logger.info(f"Max Concurrent Tasks: {max_concurrent}")

    # Create state manager
    state_manager = RedisStateManager(redis_host, redis_port)

    # Create agent instance
    agent_class = AGENT_CLASSES[agent_type]
    agent = agent_class(agent_id=agent_id, max_concurrent_tasks=max_concurrent)

    # Register with orchestrator
    agent_info = AgentInfo(
        agent_id=agent_id,
        agent_type=agent_type,
        endpoint=f"{agent_id}:50052",  # In production, use actual hostname
        capabilities=agent.get_capabilities(),
        max_concurrent_tasks=max_concurrent,
        current_tasks=0,
        healthy=True,
        last_heartbeat=time.time(),
        metadata={"version": "1.0.0"}
    )

    success = state_manager.register_agent(agent_info)
    if not success:
        logger.error("Failed to register agent with orchestrator")
        return

    logger.info(f"Agent registered successfully: {agent_id}")

    # Start heartbeat task
    async def send_heartbeat():
        while True:
            try:
                state_manager.update_agent_heartbeat(agent_id)
                await asyncio.sleep(10)  # Heartbeat every 10 seconds
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(10)

    heartbeat_task = asyncio.create_task(send_heartbeat())

    # Main agent loop - wait for tasks
    # In production, this would listen on gRPC for task requests
    logger.info(f"Agent {agent_id} is running and ready for tasks...")

    # Wait for shutdown signal
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await shutdown_event.wait()

    # Shutdown
    logger.info("Shutting down agent...")
    heartbeat_task.cancel()
    await agent.shutdown()

    logger.info("Agent service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
