"""
Unit tests for Agent implementations
"""

import pytest
import asyncio
from agents.base_agent import AgentInput
from agents.data_ingest_agent import DataIngestAgent
from agents.data_analysis_agent import DataAnalysisAgent
from agents.synthesis_agent import SynthesisAgent
from agents.video_detection_agent import VideoDetectionAgent
from agents.alerting_agent import AlertingAgent
from agents.api_caller_agent import APICallerAgent


class TestDataIngestAgent:
    """Test suite for Data Ingest Agent"""

    @pytest.mark.asyncio
    async def test_process_text_input(self):
        """Test text input processing"""
        agent = DataIngestAgent(agent_id="test-ingest-1")

        inputs = [
            AgentInput(
                input_id="input-1",
                input_type="text",
                data="Sample text for processing",
                metadata={}
            )
        ]

        output = await agent.process(inputs, {})

        assert output.output_type == "ingested_data"
        assert output.data["count"] == 1
        assert "text" in output.data["types"]

    @pytest.mark.asyncio
    async def test_process_json_input(self):
        """Test JSON input processing"""
        agent = DataIngestAgent(agent_id="test-ingest-2")

        inputs = [
            AgentInput(
                input_id="input-1",
                input_type="json",
                data='{"key": "value", "number": 42}',
                metadata={}
            )
        ]

        output = await agent.process(inputs, {})

        assert output.output_type == "ingested_data"
        assert len(output.data["records"]) == 1

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test agent health check"""
        agent = DataIngestAgent(agent_id="test-ingest-3")

        health = agent.get_health()

        assert health["healthy"] is True
        assert health["agent_type"] == "data_ingest"
        assert health["current_tasks"] == 0


class TestDataAnalysisAgent:
    """Test suite for Data Analysis Agent"""

    @pytest.mark.asyncio
    async def test_analysis_with_data(self):
        """Test data analysis"""
        agent = DataAnalysisAgent(agent_id="test-analysis-1")

        inputs = [
            AgentInput(
                input_id="input-1",
                input_type="json",
                data={"value": 42, "metric": 100},
                metadata={}
            )
        ]

        output = await agent.process(inputs, {})

        assert output.output_type == "analysis_result"
        assert "summary_statistics" in output.data
        assert "insights" in output.data
        assert "anomalies" in output.data

    @pytest.mark.asyncio
    async def test_statistics_computation(self):
        """Test statistical computation"""
        agent = DataAnalysisAgent(agent_id="test-analysis-2")

        # Create data with numeric values
        data_records = [
            {"value": 10},
            {"value": 20},
            {"value": 30},
            {"value": 40},
            {"value": 50}
        ]

        stats = await agent._compute_statistics(data_records)

        assert stats["count"] > 0
        assert "mean" in stats
        assert "median" in stats


class TestSynthesisAgent:
    """Test suite for Synthesis Agent"""

    @pytest.mark.asyncio
    async def test_report_generation(self):
        """Test report generation from analysis"""
        agent = SynthesisAgent(agent_id="test-synthesis-1")

        analysis_data = {
            "summary_statistics": {"count": 100, "mean": 50.0},
            "insights": ["Pattern detected"],
            "anomalies": [],
            "trends": ["Increasing"]
        }

        inputs = [
            AgentInput(
                input_id="input-1",
                input_type="analysis_result",
                data=analysis_data,
                metadata={}
            )
        ]

        output = await agent.process(inputs, {})

        assert output.output_type == "json_report"
        assert "report_id" in output.data
        assert "executive_summary" in output.data
        assert "detailed_findings" in output.data
        assert "recommendations" in output.data


class TestVideoDetectionAgent:
    """Test suite for Video Detection Agent"""

    @pytest.mark.asyncio
    async def test_video_processing(self):
        """Test video detection"""
        agent = VideoDetectionAgent(agent_id="test-video-1")

        inputs = [
            AgentInput(
                input_id="frame-1",
                input_type="video",
                data=b"fake_video_data",
                metadata={"fps": 30, "resolution": "1920x1080"}
            )
        ]

        output = await agent.process(inputs, {})

        assert output.output_type == "detections"
        assert "detections" in output.data
        assert output.data["detection_count"] > 0

    @pytest.mark.asyncio
    async def test_event_detection(self):
        """Test event detection from objects"""
        agent = VideoDetectionAgent(agent_id="test-video-2")

        objects = [
            {"class": "person", "confidence": 0.95},
            {"class": "person", "confidence": 0.92},
            {"class": "person", "confidence": 0.88},
            {"class": "person", "confidence": 0.85},
            {"class": "person", "confidence": 0.91},
            {"class": "person", "confidence": 0.94},
        ]

        events = await agent._detect_events(objects, {"max_persons": 5})

        assert len(events) > 0
        assert events[0]["event_type"] == "crowd_detected"


class TestAlertingAgent:
    """Test suite for Alerting Agent"""

    @pytest.mark.asyncio
    async def test_alert_generation(self):
        """Test alert generation"""
        agent = AlertingAgent(agent_id="test-alert-1")

        detections_data = {
            "detections": [
                {
                    "frame_id": "frame-1",
                    "events": [
                        {
                            "event_type": "crowd_detected",
                            "severity": "high",
                            "description": "Too many people",
                            "timestamp": 1234567890
                        }
                    ]
                }
            ]
        }

        inputs = [
            AgentInput(
                input_id="input-1",
                input_type="detections",
                data=detections_data,
                metadata={}
            )
        ]

        output = await agent.process(inputs, {})

        assert output.output_type == "alerts"
        assert output.data["alert_count"] > 0
        assert len(output.data["alerts"]) > 0

    @pytest.mark.asyncio
    async def test_alert_deduplication(self):
        """Test alert deduplication"""
        agent = AlertingAgent(agent_id="test-alert-2")

        # Create duplicate alerts
        alerts = [
            {
                "alert_id": "alert-1",
                "type": "test",
                "severity": "low",
                "message": "Test",
                "timestamp": 12345
            },
            {
                "alert_id": "alert-1",
                "type": "test",
                "severity": "low",
                "message": "Test",
                "timestamp": 12346
            }
        ]

        unique = agent._deduplicate_alerts(alerts)

        # Only first alert should remain
        assert len(unique) == 1


class TestAPICallerAgent:
    """Test suite for API Caller Agent"""

    @pytest.mark.asyncio
    async def test_api_call_success(self):
        """Test successful API call"""
        agent = APICallerAgent(agent_id="test-api-1")

        inputs = [
            AgentInput(
                input_id="input-1",
                input_type="json",
                data={"key": "value"},
                metadata={"endpoint": "http://api.example.com/test"}
            )
        ]

        parameters = {
            "endpoint": "http://api.example.com/test",
            "method": "POST"
        }

        output = await agent.process(inputs, parameters)

        assert output.output_type == "api_response"
        assert "responses" in output.data

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        agent = APICallerAgent(agent_id="test-api-2")

        endpoint = "http://failing-api.example.com"

        # Record failures to open circuit
        for _ in range(5):
            agent._record_failure(endpoint)

        # Circuit should be open
        assert agent._is_circuit_open(endpoint) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
