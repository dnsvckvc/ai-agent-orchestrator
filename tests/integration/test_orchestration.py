"""
Integration tests for end-to-end orchestration
Tests complete workflows from task submission to completion
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from core.orchestrator import Orchestrator, TaskDefinition
from core.execution_engine import ExecutionMode
from state.redis_manager import RedisStateManager, AgentInfo


@pytest.fixture
def mock_redis():
    """Mock Redis for integration tests"""
    with patch('state.redis_manager.redis.Redis') as mock:
        redis_client = Mock()
        mock.return_value = redis_client
        redis_client.ping.return_value = True
        redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [True, 1]
        redis_client.get.return_value = None
        redis_client.smembers.return_value = set()
        redis_client.zcard.return_value = 0
        redis_client.zpopmin.return_value = []
        yield redis_client


@pytest.fixture
async def orchestrator(mock_redis):
    """Create orchestrator instance"""
    orch = Orchestrator(redis_host="localhost", redis_port=6379)
    await orch.start()
    yield orch
    await orch.stop()


class TestReportGenerationWorkflow:
    """Test Use Case 1: Report Generation"""

    @pytest.mark.asyncio
    async def test_report_generation_task_submission(self, orchestrator):
        """Test submitting a report generation task"""
        task_def = TaskDefinition(
            task_id="report-001",
            task_type="report_generation",
            inputs=[
                {"input_id": "1", "type": "text", "data": "Sample data"},
                {"input_id": "2", "type": "image", "data": "image_bytes"}
            ],
            execution_mode=ExecutionMode.SEQUENTIAL,
            priority=5,
            timeout_ms=30000,
            metadata={"report_title": "Test Report"}
        )

        response = await orchestrator.submit_task(task_def)

        assert response["status"] == "queued"
        assert response["task_id"] == "report-001"
        assert "estimated_completion_ms" in response

    @pytest.mark.asyncio
    async def test_report_generation_full_pipeline(self, orchestrator, mock_redis):
        """Test full report generation pipeline"""
        # Register mock agents
        for agent_type in ["data_ingest", "data_analysis", "synthesis"]:
            agent_info = AgentInfo(
                agent_id=f"agent-{agent_type}-1",
                agent_type=agent_type,
                endpoint=f"localhost:5005{agent_type[0]}",
                capabilities=[agent_type],
                max_concurrent_tasks=10,
                current_tasks=0,
                healthy=True,
                last_heartbeat=time.time(),
                metadata={}
            )
            orchestrator.state_manager.register_agent(agent_info)

        task_def = TaskDefinition(
            task_id="report-002",
            task_type="report_generation",
            inputs=[{"input_id": "1", "type": "text", "data": "Test"}],
            execution_mode=ExecutionMode.SEQUENTIAL,
            priority=5,
            timeout_ms=30000,
            metadata={"report_title": "Full Pipeline Test"}
        )

        # Submit task
        submit_response = await orchestrator.submit_task(task_def)
        assert submit_response["status"] == "queued"

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check status
        status = await orchestrator.get_task_status("report-002")
        assert status is not None


class TestRealTimeMonitoringWorkflow:
    """Test Use Case 2: Real-Time Monitoring"""

    @pytest.mark.asyncio
    async def test_monitoring_task_submission(self, orchestrator):
        """Test submitting a monitoring task"""
        task_def = TaskDefinition(
            task_id="monitor-001",
            task_type="real_time_monitoring",
            inputs=[
                {"input_id": "video-1", "type": "video", "data": b"video_stream"}
            ],
            execution_mode=ExecutionMode.PARALLEL,
            priority=8,
            timeout_ms=5000,
            metadata={"max_persons": 10, "restricted_area": True}
        )

        response = await orchestrator.submit_task(task_def)

        assert response["status"] == "queued"
        assert response["task_id"] == "monitor-001"

    @pytest.mark.asyncio
    async def test_monitoring_with_alerts(self, orchestrator):
        """Test monitoring workflow with alert generation"""
        # Register video and alerting agents
        for agent_type in ["video_detection", "alerting"]:
            agent_info = AgentInfo(
                agent_id=f"agent-{agent_type}-1",
                agent_type=agent_type,
                endpoint=f"localhost:5005{agent_type[0]}",
                capabilities=[agent_type],
                max_concurrent_tasks=10,
                current_tasks=0,
                healthy=True,
                last_heartbeat=time.time(),
                metadata={}
            )
            orchestrator.state_manager.register_agent(agent_info)

        task_def = TaskDefinition(
            task_id="monitor-002",
            task_type="real_time_monitoring",
            inputs=[{"input_id": "v1", "type": "video", "data": b"stream"}],
            execution_mode=ExecutionMode.SEQUENTIAL,
            priority=9,
            timeout_ms=5000,
            metadata={}
        )

        response = await orchestrator.submit_task(task_def)
        assert response["status"] == "queued"


class TestTaskManagement:
    """Test task lifecycle management"""

    @pytest.mark.asyncio
    async def test_get_task_status(self, orchestrator):
        """Test retrieving task status"""
        task_def = TaskDefinition(
            task_id="status-test-001",
            task_type="data_analysis",
            inputs=[{"input_id": "1", "type": "json", "data": {}}],
            execution_mode=ExecutionMode.PARALLEL,
            priority=5,
            timeout_ms=10000,
            metadata={}
        )

        await orchestrator.submit_task(task_def)

        status = await orchestrator.get_task_status("status-test-001")
        assert status is not None
        assert status["task_id"] == "status-test-001"

    @pytest.mark.asyncio
    async def test_cancel_task(self, orchestrator):
        """Test cancelling a task"""
        task_def = TaskDefinition(
            task_id="cancel-test-001",
            task_type="data_analysis",
            inputs=[{"input_id": "1", "type": "json", "data": {}}],
            execution_mode=ExecutionMode.PARALLEL,
            priority=5,
            timeout_ms=30000,
            metadata={}
        )

        await orchestrator.submit_task(task_def)

        # Cancel task
        result = await orchestrator.cancel_task("cancel-test-001", "User requested")
        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_task_submissions(self, orchestrator):
        """Test handling multiple concurrent task submissions"""
        tasks = []

        for i in range(10):
            task_def = TaskDefinition(
                task_id=f"concurrent-{i}",
                task_type="data_analysis",
                inputs=[{"input_id": f"input-{i}", "type": "json", "data": {}}],
                execution_mode=ExecutionMode.PARALLEL,
                priority=5,
                timeout_ms=10000,
                metadata={}
            )
            tasks.append(orchestrator.submit_task(task_def))

        # Submit all tasks concurrently
        responses = await asyncio.gather(*tasks)

        # All should be queued
        assert all(r["status"] == "queued" for r in responses)
        assert len(responses) == 10


class TestFaultTolerance:
    """Test fault tolerance and recovery"""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, orchestrator):
        """Test task retry on failure"""
        task_def = TaskDefinition(
            task_id="retry-test-001",
            task_type="api_call",
            inputs=[{"input_id": "1", "type": "json", "data": {}}],
            execution_mode=ExecutionMode.PARALLEL,
            priority=5,
            timeout_ms=5000,
            metadata={}
        )

        response = await orchestrator.submit_task(task_def)
        assert response["status"] == "queued"

        # Task will fail and retry automatically

    @pytest.mark.asyncio
    async def test_agent_health_monitoring(self, orchestrator):
        """Test agent health monitoring"""
        # Register healthy agent
        agent_info = AgentInfo(
            agent_id="health-test-agent",
            agent_type="test",
            endpoint="localhost:50052",
            capabilities=["test"],
            max_concurrent_tasks=10,
            current_tasks=0,
            healthy=True,
            last_heartbeat=time.time(),
            metadata={}
        )

        orchestrator.state_manager.register_agent(agent_info)

        # Verify agent is registered
        agent = orchestrator.state_manager.get_agent("health-test-agent")
        assert agent is not None
        assert agent.healthy is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
