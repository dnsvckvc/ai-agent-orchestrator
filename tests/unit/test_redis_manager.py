"""
Unit tests for Redis State Manager
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from state.redis_manager import RedisStateManager, TaskState, TaskStatus, AgentInfo


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    with patch('state.redis_manager.redis.Redis') as mock:
        redis_client = MagicMock()
        mock.return_value = redis_client
        redis_client.ping.return_value = True
        yield redis_client


@pytest.fixture
def state_manager(mock_redis):
    """Create state manager with mocked Redis"""
    return RedisStateManager()


class TestRedisStateManager:
    """Test suite for Redis State Manager"""

    def test_initialization(self, state_manager, mock_redis):
        """Test state manager initialization"""
        assert state_manager.redis_client is not None
        mock_redis.ping.assert_called_once()

    def test_create_task(self, state_manager, mock_redis):
        """Test task creation"""
        task_state = TaskState(
            task_id="test-123",
            status=TaskStatus.QUEUED,
            task_type="test_type",
            created_at=time.time(),
            updated_at=time.time(),
            agent_executions=[],
            metadata={"test": "data"}
        )

        mock_redis.pipeline.return_value.__enter__.return_value.execute.return_value = [True, 1]

        result = state_manager.create_task(task_state)

        assert result is True
        mock_redis.pipeline.assert_called_once()

    def test_get_task(self, state_manager, mock_redis):
        """Test task retrieval"""
        task_data = {
            "task_id": "test-123",
            "status": "queued",
            "task_type": "test",
            "created_at": time.time(),
            "updated_at": time.time(),
            "agent_executions": [],
            "metadata": {},
            "retry_count": 0,
            "priority": 5
        }

        import json
        mock_redis.get.return_value = json.dumps(task_data)

        task = state_manager.get_task("test-123")

        assert task is not None
        assert task.task_id == "test-123"
        assert task.status == TaskStatus.QUEUED

    def test_update_task_status(self, state_manager, mock_redis):
        """Test task status update"""
        task_data = {
            "task_id": "test-123",
            "status": "queued",
            "task_type": "test",
            "created_at": time.time(),
            "updated_at": time.time(),
            "agent_executions": [],
            "metadata": {},
            "retry_count": 0,
            "priority": 5
        }

        import json
        mock_redis.get.return_value = json.dumps(task_data)
        mock_redis.set.return_value = True
        mock_redis.publish.return_value = 1

        result = state_manager.update_task_status(
            "test-123",
            TaskStatus.RUNNING
        )

        assert result is True
        mock_redis.set.assert_called_once()
        mock_redis.publish.assert_called_once()

    def test_register_agent(self, state_manager, mock_redis):
        """Test agent registration"""
        agent_info = AgentInfo(
            agent_id="agent-1",
            agent_type="test_agent",
            endpoint="localhost:50052",
            capabilities=["test"],
            max_concurrent_tasks=10,
            current_tasks=0,
            healthy=True,
            last_heartbeat=time.time(),
            metadata={}
        )

        mock_redis.set.return_value = True
        mock_redis.sadd.return_value = 1

        result = state_manager.register_agent(agent_info)

        assert result is True
        mock_redis.set.assert_called_once()
        mock_redis.sadd.assert_called_once()

    def test_get_agents_by_type(self, state_manager, mock_redis):
        """Test retrieving agents by type"""
        agent_data = {
            "agent_id": "agent-1",
            "agent_type": "test_agent",
            "endpoint": "localhost:50052",
            "capabilities": ["test"],
            "max_concurrent_tasks": 10,
            "current_tasks": 0,
            "healthy": True,
            "last_heartbeat": time.time(),
            "metadata": {}
        }

        import json
        mock_redis.smembers.return_value = {"agent-1"}
        mock_redis.get.return_value = json.dumps(agent_data)

        agents = state_manager.get_agents_by_type("test_agent")

        assert len(agents) == 1
        assert agents[0].agent_id == "agent-1"

    def test_acquire_lock(self, state_manager, mock_redis):
        """Test distributed lock acquisition"""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock

        lock = state_manager.acquire_lock("test-lock")

        assert lock is not None
        mock_lock.acquire.assert_called_once()

    def test_health_check(self, state_manager, mock_redis):
        """Test health check"""
        mock_redis.ping.return_value = True

        result = state_manager.health_check()

        assert result is True
        mock_redis.ping.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
