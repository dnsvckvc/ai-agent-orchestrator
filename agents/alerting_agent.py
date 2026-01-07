"""
Alerting Agent - Generates and dispatches alerts based on detections
Handles alert prioritization, deduplication, and notification
"""

import asyncio
import time
import hashlib
from typing import List, Dict, Any
import logging

from agents.base_agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class AlertingAgent(BaseAgent):
    """
    Processes detection results and generates alerts
    Handles alert prioritization, deduplication, and routing
    """

    def __init__(self, agent_id: str = None, max_concurrent_tasks: int = 20):
        super().__init__(agent_id, "alerting", max_concurrent_tasks)
        self.alert_cache = {}  # For deduplication
        self.alert_cooldown = 60  # seconds

    async def process(self, inputs: List[AgentInput], parameters: Dict[str, Any]) -> AgentOutput:
        """
        Generate alerts from detection results
        """
        start_time = asyncio.get_event_loop().time()

        alerts = []

        for inp in inputs:
            if inp.input_type == "detections":
                detections_data = inp.data
                detection_alerts = await self._generate_alerts(detections_data, parameters)
                alerts.extend(detection_alerts)

        # Deduplicate alerts
        unique_alerts = self._deduplicate_alerts(alerts)

        # Prioritize alerts
        prioritized_alerts = self._prioritize_alerts(unique_alerts)

        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

        return AgentOutput(
            output_type="alerts",
            data={
                "alerts": prioritized_alerts,
                "alert_count": len(prioritized_alerts),
                "timestamp": time.time()
            },
            metadata={
                "agent_id": self.agent_id,
                "total_generated": len(alerts),
                "after_dedup": len(unique_alerts),
                "processing_time_ms": processing_time
            },
            processing_time_ms=processing_time
        )

    async def _generate_alerts(self, detections_data: Dict[str, Any],
                               parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts from detection events"""
        alerts = []

        detections = detections_data.get("detections", [])

        for detection in detections:
            events = detection.get("events", [])

            for event in events:
                alert = {
                    "alert_id": self._generate_alert_id(event),
                    "type": event["event_type"],
                    "severity": event["severity"],
                    "message": event["description"],
                    "timestamp": event["timestamp"],
                    "source": {
                        "agent_id": self.agent_id,
                        "detection_frame": detection.get("frame_id"),
                        "objects": detection.get("objects", [])
                    },
                    "metadata": {
                        "requires_action": event["severity"] in ["high", "critical"],
                        "auto_escalate": event["severity"] == "critical"
                    }
                }

                alerts.append(alert)

        return alerts

    def _generate_alert_id(self, event: Dict[str, Any]) -> str:
        """Generate unique alert ID"""
        # Create hash from event type and key properties
        content = f"{event['event_type']}_{event.get('description', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _deduplicate_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate alerts within cooldown period"""
        current_time = time.time()
        unique_alerts = []

        for alert in alerts:
            alert_id = alert["alert_id"]

            # Check if alert was recently sent
            if alert_id in self.alert_cache:
                last_sent = self.alert_cache[alert_id]
                if current_time - last_sent < self.alert_cooldown:
                    logger.debug(f"Suppressing duplicate alert {alert_id}")
                    continue

            # Add to unique alerts and cache
            unique_alerts.append(alert)
            self.alert_cache[alert_id] = current_time

        # Cleanup old cache entries
        self._cleanup_cache(current_time)

        return unique_alerts

    def _cleanup_cache(self, current_time: float):
        """Remove old entries from alert cache"""
        expired_ids = [
            alert_id for alert_id, timestamp in self.alert_cache.items()
            if current_time - timestamp > self.alert_cooldown * 2
        ]

        for alert_id in expired_ids:
            del self.alert_cache[alert_id]

    def _prioritize_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize alerts by severity"""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        sorted_alerts = sorted(
            alerts,
            key=lambda a: severity_order.get(a["severity"], 999)
        )

        return sorted_alerts
