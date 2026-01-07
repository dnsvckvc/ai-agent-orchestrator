"""
API Caller Agent - Makes external API calls with retry logic and circuit breaker
Handles REST APIs, GraphQL, and webhooks with fault tolerance
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agents.base_agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class APICallerAgent(BaseAgent):
    """
    Makes external API calls with intelligent retry and circuit breaker patterns
    Supports REST, GraphQL, and webhook integrations
    """

    def __init__(self, agent_id: str = None, max_concurrent_tasks: int = 25):
        super().__init__(agent_id, "api_caller", max_concurrent_tasks)
        self.circuit_breaker_threshold = 5  # failures before opening circuit
        self.circuit_breaker_timeout = 60  # seconds
        self.failed_endpoints = {}  # Track failures per endpoint

    async def process(self, inputs: List[AgentInput], parameters: Dict[str, Any]) -> AgentOutput:
        """
        Make API calls with retry logic and circuit breaker
        """
        start_time = asyncio.get_event_loop().time()

        results = []

        for inp in inputs:
            # Extract API call parameters
            endpoint = parameters.get("endpoint") or inp.metadata.get("endpoint")
            method = parameters.get("method", "GET").upper()
            headers = parameters.get("headers", {})
            payload = inp.data if inp.input_type == "json" else None

            if not endpoint:
                results.append({
                    "status": "error",
                    "error": "No endpoint provided"
                })
                continue

            # Check circuit breaker
            if self._is_circuit_open(endpoint):
                results.append({
                    "status": "circuit_open",
                    "endpoint": endpoint,
                    "message": "Circuit breaker is open - endpoint unavailable"
                })
                continue

            # Make API call with retry
            try:
                response = await self._make_api_call(endpoint, method, headers, payload)
                results.append(response)
                self._record_success(endpoint)

            except Exception as e:
                logger.error(f"API call to {endpoint} failed: {e}")
                self._record_failure(endpoint)
                results.append({
                    "status": "error",
                    "endpoint": endpoint,
                    "error": str(e)
                })

        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

        return AgentOutput(
            output_type="api_response",
            data={
                "responses": results,
                "success_count": sum(1 for r in results if r.get("status") == "success"),
                "error_count": sum(1 for r in results if r.get("status") == "error")
            },
            metadata={
                "agent_id": self.agent_id,
                "processing_time_ms": processing_time
            },
            processing_time_ms=processing_time
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def _make_api_call(self, endpoint: str, method: str,
                            headers: Dict[str, str], payload: Optional[Dict]) -> Dict[str, Any]:
        """
        Make actual API call with retry logic
        In production, this would use aiohttp or httpx
        """
        # Simulate API call
        await asyncio.sleep(0.1)  # Simulate network latency

        # Simulate random failures (10% chance for testing)
        import random
        if random.random() < 0.1:
            raise ConnectionError("Simulated connection error")

        # Mock successful response
        response = {
            "status": "success",
            "endpoint": endpoint,
            "method": method,
            "status_code": 200,
            "data": {
                "message": "API call successful",
                "timestamp": time.time()
            },
            "response_time_ms": 100
        }

        return response

    def _is_circuit_open(self, endpoint: str) -> bool:
        """Check if circuit breaker is open for endpoint"""
        if endpoint not in self.failed_endpoints:
            return False

        failure_data = self.failed_endpoints[endpoint]
        failure_count = failure_data.get("count", 0)
        last_failure = failure_data.get("last_failure", 0)

        # Check if circuit should be opened
        if failure_count >= self.circuit_breaker_threshold:
            # Check if timeout has passed (circuit can close)
            if time.time() - last_failure > self.circuit_breaker_timeout:
                # Half-open: reset and try again
                self.failed_endpoints[endpoint] = {"count": 0, "last_failure": 0}
                logger.info(f"Circuit breaker for {endpoint} moved to half-open state")
                return False
            else:
                logger.warning(f"Circuit breaker open for {endpoint}")
                return True

        return False

    def _record_failure(self, endpoint: str):
        """Record API call failure"""
        if endpoint not in self.failed_endpoints:
            self.failed_endpoints[endpoint] = {"count": 0, "last_failure": 0}

        self.failed_endpoints[endpoint]["count"] += 1
        self.failed_endpoints[endpoint]["last_failure"] = time.time()

        logger.warning(
            f"Recorded failure for {endpoint}: "
            f"{self.failed_endpoints[endpoint]['count']} failures"
        )

    def _record_success(self, endpoint: str):
        """Record successful API call - reset circuit breaker"""
        if endpoint in self.failed_endpoints:
            del self.failed_endpoints[endpoint]
