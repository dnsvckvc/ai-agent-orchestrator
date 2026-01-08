"""
Industry Synthesis Agent - Aggregates summaries and provides meta-analysis.

This agent analyzes multiple summaries from various sources (podcasts, documents)
and provides high-level insights about:
- Cross-cutting themes and trends
- Industry-specific developments
- Emerging topics and patterns
- Frequency analysis of key concepts
- Executive-level intelligence reports
"""
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter
import json

from agents.base_agent import BaseAgent, AgentInput, AgentOutput
from storage import FileStorage, StorageConfig, MarkdownBuilder
from llm import LLMClient, LLMProvider, LLMConfig

logger = logging.getLogger(__name__)


class IndustrySynthesisAgent(BaseAgent):
    """
    Agent that synthesizes insights from multiple summaries.

    Capabilities:
    - Aggregate insights from multiple sources
    - Identify cross-cutting themes
    - Analyze trends over time
    - Group by industry/topic
    - Generate executive intelligence reports
    - Frequency analysis of concepts
    - Comparative analysis across sources
    """

    def __init__(
        self,
        agent_id: str,
        llm_config: Optional[LLMConfig] = None,
        storage_config: Optional[StorageConfig] = None
    ):
        super().__init__(agent_id, "industry_synthesis")

        # Initialize LLM client
        if llm_config:
            self.llm_client = LLMClient(llm_config)
        else:
            provider = os.getenv("LLM_PROVIDER", "openai")
            model = os.getenv("LLM_MODEL")
            self.llm_client = LLMClient.from_env(provider=provider, model=model)

        # Initialize file storage
        self.storage = FileStorage(storage_config or StorageConfig(
            base_dir="./output",
            organize_by_date=True,
            organize_by_type=True
        ))

        logger.info(f"IndustrySynthesisAgent {agent_id} initialized")

    async def process(
        self,
        inputs: List[AgentInput],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentOutput:
        """
        Process multiple summaries and generate synthesis report.

        Input types:
        - "summary": Individual summary data
        - "summary_file": Path to summary file
        - "summaries_batch": List of summaries

        Parameters:
        - report_type: "daily", "weekly", "monthly" (affects depth)
        - industries: List of industries to focus on
        - include_trends: Include trend analysis (default: True)
        - include_topics: Include topic frequency (default: True)
        - include_comparison: Compare sources (default: True)
        - min_frequency: Minimum mentions for topic inclusion (default: 2)
        - save_to_storage: Save report (default: True)

        Returns:
        - Synthesis report with aggregated insights
        """
        parameters = parameters or {}
        report_type = parameters.get("report_type", "weekly")
        industries = parameters.get("industries", [])
        include_trends = parameters.get("include_trends", True)
        include_topics = parameters.get("include_topics", True)
        include_comparison = parameters.get("include_comparison", True)
        min_frequency = parameters.get("min_frequency", 2)
        save_to_storage = parameters.get("save_to_storage", True)

        try:
            # Collect all summaries
            summaries = await self._collect_summaries(inputs)

            if not summaries:
                logger.warning("No summaries provided for synthesis")
                return AgentOutput(
                    output_type="synthesis_report",
                    data={"error": "No summaries to synthesize"},
                    metadata={},
                    processing_time_ms=0
                )

            # Perform analysis
            analysis = await self._analyze_summaries(
                summaries,
                report_type=report_type,
                industries=industries,
                include_trends=include_trends,
                include_topics=include_topics,
                include_comparison=include_comparison,
                min_frequency=min_frequency
            )

            # Generate synthesis report
            report = await self._generate_synthesis_report(
                summaries,
                analysis,
                report_type
            )

            # Format as markdown
            formatted_report = self._format_as_markdown(
                report,
                analysis,
                report_type
            )

            # Save to storage if requested
            file_path = None
            if save_to_storage:
                file_path = self._save_report(
                    formatted_report,
                    report,
                    analysis,
                    report_type
                )

            return AgentOutput(
                output_type="synthesis_report",
                data={
                    "report": report,
                    "analysis": analysis,
                    "file_path": file_path,
                    "summary_count": len(summaries),
                    "created_at": datetime.now().isoformat()
                },
                metadata={
                    "report_type": report_type,
                    "industries": industries,
                    "llm_model": self.llm_client.config.model
                },
                processing_time_ms=0
            )

        except Exception as e:
            logger.error(f"Error generating synthesis report: {e}", exc_info=True)
            return AgentOutput(
                output_type="synthesis_report",
                data={"error": str(e), "status": "failed"},
                metadata={},
                processing_time_ms=0
            )

    async def _collect_summaries(self, inputs: List[AgentInput]) -> List[Dict[str, Any]]:
        """Collect and normalize summaries from various input formats."""
        summaries = []

        for agent_input in inputs:
            if agent_input.input_type == "summary":
                # Direct summary data
                summaries.append(agent_input.data)

            elif agent_input.input_type == "summary_file":
                # Load from file
                content, metadata = self.storage.load_markdown(agent_input.data)
                summaries.append({
                    "content": content,
                    "metadata": metadata
                })

            elif agent_input.input_type == "summaries_batch":
                # Multiple summaries in one input
                if isinstance(agent_input.data, list):
                    summaries.extend(agent_input.data)

        return summaries

    async def _analyze_summaries(
        self,
        summaries: List[Dict[str, Any]],
        report_type: str,
        industries: List[str],
        include_trends: bool,
        include_topics: bool,
        include_comparison: bool,
        min_frequency: int
    ) -> Dict[str, Any]:
        """
        Perform statistical and thematic analysis on summaries.

        Returns structured analysis data.
        """
        analysis = {
            "total_summaries": len(summaries),
            "date_range": self._get_date_range(summaries),
            "sources": self._analyze_sources(summaries),
        }

        # Topic frequency analysis
        if include_topics:
            analysis["topics"] = self._analyze_topics(summaries, min_frequency)

        # Trend analysis
        if include_trends:
            analysis["trends"] = self._analyze_trends(summaries)

        # Industry breakdown
        if industries:
            analysis["industries"] = self._analyze_by_industry(summaries, industries)

        # Source comparison
        if include_comparison:
            analysis["comparison"] = self._compare_sources(summaries)

        return analysis

    def _get_date_range(self, summaries: List[Dict[str, Any]]) -> Dict[str, str]:
        """Get date range of summaries."""
        dates = []

        for summary in summaries:
            metadata = summary.get("metadata", {})
            date_str = metadata.get("publish_date") or metadata.get("date")

            if date_str:
                try:
                    # Try to parse ISO format
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    dates.append(date)
                except Exception:
                    pass

        if dates:
            return {
                "start": min(dates).isoformat(),
                "end": max(dates).isoformat(),
                "span_days": (max(dates) - min(dates)).days
            }

        return {"start": None, "end": None, "span_days": 0}

    def _analyze_sources(self, summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze source distribution."""
        source_types = Counter()
        source_names = Counter()

        for summary in summaries:
            metadata = summary.get("metadata", {})

            source_type = metadata.get("source_type", "unknown")
            source_types[source_type] += 1

            source_name = (
                metadata.get("podcast_name") or
                metadata.get("source") or
                "Unknown"
            )
            source_names[source_name] += 1

        return {
            "by_type": dict(source_types),
            "by_name": dict(source_names.most_common(10))
        }

    def _analyze_topics(
        self,
        summaries: List[Dict[str, Any]],
        min_frequency: int
    ) -> Dict[str, Any]:
        """Analyze topic frequency across summaries."""
        all_topics = []

        # Extract topics from each summary
        for summary in summaries:
            # Try to get topics from summary data
            if isinstance(summary.get("summary"), dict):
                topics = summary["summary"].get("topics", [])
                all_topics.extend(topics)

            # Also check in metadata
            metadata = summary.get("metadata", {})
            if "topics" in metadata:
                all_topics.extend(metadata["topics"])

            # Check industry tags
            if isinstance(summary.get("summary"), dict):
                tags = summary["summary"].get("industry_tags", [])
                all_topics.extend(tags)

        # Count frequencies
        topic_counts = Counter(all_topics)

        # Filter by minimum frequency
        filtered_topics = {
            topic: count
            for topic, count in topic_counts.items()
            if count >= min_frequency
        }

        return {
            "total_unique": len(topic_counts),
            "above_threshold": len(filtered_topics),
            "top_topics": dict(Counter(filtered_topics).most_common(20)),
            "frequency_distribution": dict(Counter(topic_counts.values()))
        }

    def _analyze_trends(self, summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends over time."""
        # Group summaries by time period
        by_week = {}

        for summary in summaries:
            metadata = summary.get("metadata", {})
            date_str = metadata.get("publish_date") or metadata.get("date")

            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    # Get week number
                    week_key = date.strftime("%Y-W%W")

                    if week_key not in by_week:
                        by_week[week_key] = []

                    by_week[week_key].append(summary)
                except Exception:
                    pass

        # Analyze growth
        if len(by_week) > 1:
            weeks = sorted(by_week.keys())
            counts = [len(by_week[w]) for w in weeks]

            trend_direction = "increasing" if counts[-1] > counts[0] else "decreasing"

            return {
                "weeks_covered": len(weeks),
                "trend_direction": trend_direction,
                "weekly_counts": {w: len(by_week[w]) for w in weeks}
            }

        return {"weeks_covered": len(by_week)}

    def _analyze_by_industry(
        self,
        summaries: List[Dict[str, Any]],
        industries: List[str]
    ) -> Dict[str, Any]:
        """Group and analyze by industry."""
        by_industry = {industry: [] for industry in industries}
        untagged = []

        for summary in summaries:
            # Get industry tags
            tags = []

            if isinstance(summary.get("summary"), dict):
                tags = summary["summary"].get("industry_tags", [])

            # Categorize
            tagged = False
            for industry in industries:
                # Simple matching - could be more sophisticated
                if any(industry.lower() in tag.lower() for tag in tags):
                    by_industry[industry].append(summary)
                    tagged = True

            if not tagged:
                untagged.append(summary)

        return {
            "distribution": {
                industry: len(summaries)
                for industry, summaries in by_industry.items()
            },
            "untagged_count": len(untagged),
            "coverage": {
                industry: len(summaries) / len(summaries) * 100
                for industry, summaries in by_industry.items()
                if len(summaries) > 0
            }
        }

    def _compare_sources(self, summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare different sources."""
        # Compare podcast vs document sources
        podcast_summaries = []
        document_summaries = []

        for summary in summaries:
            metadata = summary.get("metadata", {})
            source_type = metadata.get("source_type", "")

            if source_type == "podcast":
                podcast_summaries.append(summary)
            elif source_type == "document":
                document_summaries.append(summary)

        comparison = {
            "podcast_count": len(podcast_summaries),
            "document_count": len(document_summaries)
        }

        # Average insights per source type
        if podcast_summaries:
            avg_podcast_insights = sum(
                len(s.get("summary", {}).get("key_insights", []))
                for s in podcast_summaries
            ) / len(podcast_summaries)
            comparison["avg_podcast_insights"] = round(avg_podcast_insights, 1)

        if document_summaries:
            avg_doc_insights = sum(
                len(s.get("summary", {}).get("key_insights", []))
                for s in document_summaries
            ) / len(document_summaries)
            comparison["avg_document_insights"] = round(avg_doc_insights, 1)

        return comparison

    async def _generate_synthesis_report(
        self,
        summaries: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        report_type: str
    ) -> Dict[str, Any]:
        """
        Generate synthesis report using LLM.

        Returns structured report data.
        """
        # Build prompt with all summaries and analysis
        system_prompt = self._build_synthesis_system_prompt(report_type)
        user_prompt = self._build_synthesis_user_prompt(summaries, analysis)

        logger.info(f"Generating {report_type} synthesis report with LLM")

        # Call LLM
        response = await self.llm_client.complete_with_system(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
            max_tokens=3000
        )

        # Parse response
        report = self._parse_synthesis_response(response.content)

        # Add metadata
        report["llm_usage"] = response.usage
        report["llm_model"] = response.model
        report["generated_at"] = datetime.now().isoformat()

        return report

    def _build_synthesis_system_prompt(self, report_type: str) -> str:
        """Build system prompt for synthesis."""
        report_scope = {
            "daily": "daily insights and immediate trends",
            "weekly": "weekly patterns and emerging themes",
            "monthly": "monthly trends and strategic insights"
        }

        scope = report_scope.get(report_type, "comprehensive analysis")

        return f"""You are an expert industry analyst specializing in synthesizing insights
from multiple sources to identify key trends and patterns.

Your task is to create a {report_type} synthesis report that provides {scope}.

Structure your analysis as follows:

## Executive Summary
Provide a high-level overview (2-3 paragraphs) of the most important findings.

## Key Themes
Identify 3-5 major themes that emerged across multiple sources. For each theme:
- Describe the theme
- Note which sources/industries it appeared in
- Assess its significance

## Emerging Trends
Highlight 3-5 emerging trends or shifts in the landscape.
- What's gaining traction
- What's declining
- What's new or surprising

## Industry-Specific Insights
Break down key findings by industry or domain.

## Cross-Cutting Insights
Identify patterns that span multiple industries or topics.

## Outlook & Implications
What do these findings suggest for the near future?
What should stakeholders pay attention to?

Base your analysis on the provided summaries and statistical data. Be specific and cite
sources when possible. Focus on actionable insights rather than generic observations."""

        return prompt

    def _build_synthesis_user_prompt(
        self,
        summaries: List[Dict[str, Any]],
        analysis: Dict[str, Any]
    ) -> str:
        """Build user prompt with summaries and analysis."""
        # Format analysis data
        analysis_text = json.dumps(analysis, indent=2)

        # Collect summary excerpts
        summary_excerpts = []

        for i, summary in enumerate(summaries[:20], 1):  # Limit to 20 for context
            metadata = summary.get("metadata", {})
            title = metadata.get("title", f"Summary {i}")
            source = (
                metadata.get("podcast_name") or
                metadata.get("source") or
                "Unknown"
            )

            # Get executive summary if available
            if isinstance(summary.get("summary"), dict):
                exec_summary = summary["summary"].get("executive_summary", "")
                insights = summary["summary"].get("key_insights", [])

                excerpt = f"### {title}\n**Source:** {source}\n\n{exec_summary}\n\n"

                if insights:
                    excerpt += "**Key Insights:**\n"
                    for insight in insights[:3]:  # First 3 insights
                        excerpt += f"- {insight}\n"

                summary_excerpts.append(excerpt)

        summaries_text = "\n\n".join(summary_excerpts)

        prompt = f"""Please analyze the following summaries and statistical analysis to create a synthesis report.

## Statistical Analysis

```json
{analysis_text}
```

## Source Summaries

{summaries_text}

{"..." if len(summaries) > 20 else ""}
{f"(Showing 20 of {len(summaries)} summaries)" if len(summaries) > 20 else ""}

---

Please provide your synthesis following the structure outlined in the system prompt."""

        return prompt

    def _parse_synthesis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM synthesis response into structured data."""
        return {
            "raw_report": response_text,
            "executive_summary": self._extract_section(response_text, "Executive Summary"),
            "key_themes": self._extract_section(response_text, "Key Themes"),
            "emerging_trends": self._extract_section(response_text, "Emerging Trends"),
            "industry_insights": self._extract_section(response_text, "Industry-Specific Insights"),
            "cross_cutting": self._extract_section(response_text, "Cross-Cutting Insights"),
            "outlook": self._extract_section(response_text, "Outlook & Implications")
        }

    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a specific section from markdown text."""
        import re

        # Find section
        pattern = f"##+ {section_name}\\n(.*?)(?=\\n##|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return ""

    def _format_as_markdown(
        self,
        report: Dict[str, Any],
        analysis: Dict[str, Any],
        report_type: str
    ) -> str:
        """Format synthesis report as markdown."""
        builder = MarkdownBuilder()

        # Frontmatter
        builder.add_frontmatter({
            "title": f"{report_type.capitalize()} Industry Synthesis Report",
            "type": "synthesis_report",
            "report_period": report_type,
            "generated_at": datetime.now().isoformat(),
            "summary_count": analysis["total_summaries"]
        })

        # Title
        date_str = datetime.now().strftime("%B %d, %Y")
        builder.add_heading(
            f"{report_type.capitalize()} Industry Synthesis Report",
            level=1
        )
        builder.add_paragraph(f"*Generated on {date_str}*")

        # Metadata section
        builder.add_horizontal_rule()
        builder.add_heading("Report Metadata", level=2)

        builder.add_paragraph(f"**Summaries Analyzed:** {analysis['total_summaries']}")

        if analysis.get("date_range", {}).get("start"):
            date_range = analysis["date_range"]
            builder.add_paragraph(
                f"**Date Range:** {date_range['start'][:10]} to {date_range['end'][:10]} "
                f"({date_range['span_days']} days)"
            )

        if analysis.get("sources"):
            sources = analysis["sources"]
            builder.add_paragraph(f"**Source Types:** {', '.join(sources['by_type'].keys())}")

        builder.add_horizontal_rule()

        # Main report content
        builder.add_custom(report.get("raw_report", ""))

        # Appendix: Statistical Analysis
        builder.add_horizontal_rule()
        builder.add_heading("Appendix: Statistical Analysis", level=2)

        # Topic frequencies
        if analysis.get("topics"):
            topics = analysis["topics"]
            builder.add_heading("Topic Frequency", level=3)
            builder.add_paragraph(
                f"Identified {topics['total_unique']} unique topics, "
                f"{topics['above_threshold']} appearing multiple times."
            )

            if topics.get("top_topics"):
                builder.add_paragraph("**Most Frequent Topics:**")
                topic_items = [
                    f"{topic} ({count} mentions)"
                    for topic, count in list(topics["top_topics"].items())[:10]
                ]
                builder.add_list(topic_items)

        # Source distribution
        if analysis.get("sources", {}).get("by_name"):
            builder.add_heading("Source Distribution", level=3)
            source_items = [
                f"{source}: {count} summaries"
                for source, count in list(analysis["sources"]["by_name"].items())[:10]
            ]
            builder.add_list(source_items)

        # Footer
        builder.add_horizontal_rule()
        builder.add_paragraph(
            f"*Report generated by Industry Synthesis Agent using "
            f"{report.get('llm_model', 'LLM')}*"
        )

        return builder.build()

    def _save_report(
        self,
        formatted_report: str,
        report_data: Dict[str, Any],
        analysis: Dict[str, Any],
        report_type: str
    ) -> str:
        """Save synthesis report to storage."""
        # Generate filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{report_type}_synthesis_{date_str}"

        # Metadata
        metadata = {
            "report_type": report_type,
            "summary_count": analysis["total_summaries"],
            "llm_model": report_data.get("llm_model"),
            "llm_usage": report_data.get("llm_usage"),
            "date_range": analysis.get("date_range")
        }

        file_path = self.storage.save_markdown(
            content=formatted_report,
            filename=filename,
            content_type="synthesis_report",
            metadata=metadata
        )

        logger.info(f"Synthesis report saved to {file_path}")
        return file_path

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "multi_source_synthesis",
            "trend_analysis",
            "topic_frequency_analysis",
            "industry_grouping",
            "comparative_analysis",
            "executive_reporting"
        ]
