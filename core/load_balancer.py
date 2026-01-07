"""
Load Balancer - Intelligent agent selection with fault tolerance
"""

import time
from typing import Optional, List
from enum import Enum
import logging

from state.redis_manager import RedisStateManager, AgentInfo

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"
    WEIGHTED = "weighted"


class LoadBalancer:
    """
    Intelligently selects agents based on load, health, and availability
    Provides fault tolerance through agent health monitoring
    """

    def __init__(self, state_manager: RedisStateManager,
                 strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED):
        self.state_manager = state_manager
        self.strategy = strategy
        self.round_robin_counters = {}

    def select_agent(self, agent_type: str) -> Optional[AgentInfo]:
        """
        Select best available agent for the given type
        Returns None if no healthy agents available
        """
        try:
            # Get all healthy agents of this type
            agents = self.state_manager.get_agents_by_type(agent_type)

            if not agents:
                logger.warning(f"No agents available for type: {agent_type}")
                return None

            # Filter out unhealthy or overloaded agents
            available_agents = [
                agent for agent in agents
                if self._is_agent_available(agent)
            ]

            if not available_agents:
                logger.warning(f"No available agents for type {agent_type} (all overloaded or unhealthy)")
                return None

            # Select based on strategy
            if self.strategy == LoadBalancingStrategy.LEAST_LOADED:
                return self._select_least_loaded(available_agents)
            elif self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                return self._select_round_robin(agent_type, available_agents)
            elif self.strategy == LoadBalancingStrategy.WEIGHTED:
                return self._select_weighted(available_agents)
            else:
                return self._select_random(available_agents)

        except Exception as e:
            logger.error(f"Error selecting agent for type {agent_type}: {e}")
            return None

    def _is_agent_available(self, agent: AgentInfo) -> bool:
        """Check if agent is available for new tasks"""
        # Check health status
        if not agent.healthy:
            return False

        # Check heartbeat recency (within last 30 seconds)
        current_time = time.time()
        if current_time - agent.last_heartbeat > 30:
            logger.warning(f"Agent {agent.agent_id} heartbeat is stale")
            return False

        # Check if agent is at capacity
        if agent.current_tasks >= agent.max_concurrent_tasks:
            return False

        return True

    def _select_least_loaded(self, agents: List[AgentInfo]) -> AgentInfo:
        """
        Select agent with least current tasks
        Best for balanced load distribution
        """
        # Sort by current tasks (ascending) and return first
        sorted_agents = sorted(agents, key=lambda a: a.current_tasks)
        selected = sorted_agents[0]

        logger.debug(f"Selected agent {selected.agent_id} (least loaded: {selected.current_tasks} tasks)")
        return selected

    def _select_round_robin(self, agent_type: str, agents: List[AgentInfo]) -> AgentInfo:
        """
        Select agents in round-robin fashion
        Ensures fair distribution
        """
        if agent_type not in self.round_robin_counters:
            self.round_robin_counters[agent_type] = 0

        index = self.round_robin_counters[agent_type] % len(agents)
        self.round_robin_counters[agent_type] += 1

        selected = agents[index]
        logger.debug(f"Selected agent {selected.agent_id} (round-robin index: {index})")
        return selected

    def _select_weighted(self, agents: List[AgentInfo]) -> AgentInfo:
        """
        Select based on agent capacity and current load
        Prefers agents with higher capacity and lower load
        """
        # Calculate score for each agent (higher is better)
        scores = []
        for agent in agents:
            # Score = available capacity
            available_capacity = agent.max_concurrent_tasks - agent.current_tasks
            utilization = agent.current_tasks / agent.max_concurrent_tasks if agent.max_concurrent_tasks > 0 else 1.0

            # Prefer lower utilization
            score = available_capacity * (1.0 - utilization)
            scores.append((score, agent))

        # Select highest score
        scores.sort(reverse=True, key=lambda x: x[0])
        selected = scores[0][1]

        logger.debug(f"Selected agent {selected.agent_id} (weighted score: {scores[0][0]:.2f})")
        return selected

    def _select_random(self, agents: List[AgentInfo]) -> AgentInfo:
        """Random selection (for testing)"""
        import random
        selected = random.choice(agents)
        logger.debug(f"Selected agent {selected.agent_id} (random)")
        return selected

    def report_agent_failure(self, agent_id: str, error: str):
        """
        Report agent failure for circuit breaker pattern
        In production, this would track failure rates and temporarily disable failing agents
        """
        logger.warning(f"Agent {agent_id} reported failure: {error}")

        # Get agent and mark as unhealthy
        agent = self.state_manager.get_agent(agent_id)
        if agent:
            agent.healthy = False
            self.state_manager.register_agent(agent)

    def report_agent_success(self, agent_id: str):
        """Report successful agent execution"""
        agent = self.state_manager.get_agent(agent_id)
        if agent and not agent.healthy:
            # Restore health if it was marked unhealthy
            agent.healthy = True
            self.state_manager.register_agent(agent)

    def get_agent_stats(self, agent_type: str) -> dict:
        """Get statistics for agents of a specific type"""
        agents = self.state_manager.get_agents_by_type(agent_type)

        total_agents = len(agents)
        healthy_agents = sum(1 for a in agents if a.healthy)
        total_capacity = sum(a.max_concurrent_tasks for a in agents)
        current_load = sum(a.current_tasks for a in agents)

        return {
            "agent_type": agent_type,
            "total_agents": total_agents,
            "healthy_agents": healthy_agents,
            "total_capacity": total_capacity,
            "current_load": current_load,
            "utilization": current_load / total_capacity if total_capacity > 0 else 0.0
        }
