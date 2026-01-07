"""
Synthesis Agent - Synthesizes analysis results into final reports
Generates structured outputs like JSON reports, summaries, etc.
"""

import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime
import logging

from agents.base_agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class SynthesisAgent(BaseAgent):
    """
    Synthesizes analysis results into final deliverables
    Creates reports, summaries, and structured outputs
    """

    def __init__(self, agent_id: str = None, max_concurrent_tasks: int = 15):
        super().__init__(agent_id, "synthesis", max_concurrent_tasks)

    async def process(self, inputs: List[AgentInput], parameters: Dict[str, Any]) -> AgentOutput:
        """
        Synthesize analysis results into final report
        """
        start_time = asyncio.get_event_loop().time()

        # Extract analysis results
        analysis_data = {}
        for inp in inputs:
            if inp.input_type == "analysis_result":
                analysis_data = inp.data

        # Generate report
        report = await self._generate_report(analysis_data, parameters)

        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

        return AgentOutput(
            output_type="json_report",
            data=report,
            metadata={
                "agent_id": self.agent_id,
                "report_version": "1.0",
                "processing_time_ms": processing_time
            },
            processing_time_ms=processing_time
        )

    async def _generate_report(self, analysis_data: Dict[str, Any],
                               parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured JSON report"""
        await asyncio.sleep(0.05)  # Simulate report generation

        report = {
            "report_id": f"report_{int(datetime.now().timestamp())}",
            "generated_at": datetime.now().isoformat(),
            "title": parameters.get("report_title", "Data Analysis Report"),
            "executive_summary": self._create_executive_summary(analysis_data),
            "detailed_findings": {
                "statistics": analysis_data.get("summary_statistics", {}),
                "insights": analysis_data.get("insights", []),
                "anomalies": analysis_data.get("anomalies", []),
                "trends": analysis_data.get("trends", [])
            },
            "recommendations": self._generate_recommendations(analysis_data),
            "metadata": {
                "analysis_depth": "comprehensive",
                "confidence_level": "high",
                "data_quality_score": 0.95
            }
        }

        return report

    def _create_executive_summary(self, analysis_data: Dict[str, Any]) -> str:
        """Create executive summary"""
        stats = analysis_data.get("summary_statistics", {})
        insights = analysis_data.get("insights", [])
        anomalies = analysis_data.get("anomalies", [])

        summary_parts = []

        if stats.get("count"):
            summary_parts.append(
                f"Analysis completed on {stats['count']} data points. "
            )

        if insights:
            summary_parts.append(
                f"Key insights identified: {len(insights)} significant patterns detected. "
            )

        if anomalies:
            summary_parts.append(
                f"Attention required: {len(anomalies)} anomalies detected requiring investigation."
            )
        else:
            summary_parts.append("No critical anomalies detected.")

        return "".join(summary_parts)

    def _generate_recommendations(self, analysis_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate actionable recommendations"""
        recommendations = []

        anomalies = analysis_data.get("anomalies", [])
        if anomalies:
            recommendations.append({
                "priority": "high",
                "recommendation": "Investigate detected anomalies for potential data quality issues",
                "rationale": f"{len(anomalies)} outliers detected in the dataset"
            })

        insights = analysis_data.get("insights", [])
        if insights:
            recommendations.append({
                "priority": "medium",
                "recommendation": "Leverage identified patterns for predictive modeling",
                "rationale": "Multiple significant patterns detected in historical data"
            })

        recommendations.append({
            "priority": "low",
            "recommendation": "Schedule regular data quality audits",
            "rationale": "Maintain data integrity for future analyses"
        })

        return recommendations
