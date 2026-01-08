"""
Transcript Summary Agent - Generates summaries and insights from transcripts.

This agent uses LLMs to analyze transcripts and extract:
- Executive summaries
- Key insights and takeaways
- Topic categorization
- Notable quotes
- Industry tags
"""
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import BaseAgent, AgentInput, AgentOutput
from storage import FileStorage, StorageConfig, MarkdownBuilder
from llm import LLMClient, LLMProvider, LLMConfig

logger = logging.getLogger(__name__)


class TranscriptSummaryAgent(BaseAgent):
    """
    Agent that generates summaries and insights from transcripts using LLMs.

    Capabilities:
    - Generate executive summaries
    - Extract key insights and takeaways
    - Identify and categorize topics
    - Extract notable quotes
    - Tag content by industry/domain
    - Support multiple LLM providers
    """

    def __init__(
        self,
        agent_id: str,
        llm_config: Optional[LLMConfig] = None,
        storage_config: Optional[StorageConfig] = None
    ):
        super().__init__(agent_id, "transcript_summary")

        # Initialize LLM client
        if llm_config:
            self.llm_client = LLMClient(llm_config)
        else:
            # Use environment-based configuration
            provider = os.getenv("LLM_PROVIDER", "openai")
            model = os.getenv("LLM_MODEL")
            self.llm_client = LLMClient.from_env(provider=provider, model=model)

        # Initialize file storage
        self.storage = FileStorage(storage_config or StorageConfig(
            base_dir="./output",
            organize_by_date=True,
            organize_by_type=True
        ))

        logger.info(f"TranscriptSummaryAgent {agent_id} initialized with LLM provider")

    async def process(
        self,
        inputs: List[AgentInput],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentOutput:
        """
        Process transcripts and generate summaries.

        Input types:
        - "transcript": Full transcript text
        - "transcript_file": Path to transcript file

        Parameters:
        - summary_length: "short" (1-2 paragraphs), "medium" (3-5), "long" (detailed)
        - include_quotes: Extract notable quotes (default: True)
        - include_topics: Identify and categorize topics (default: True)
        - include_insights: Extract key insights (default: True)
        - industry_tags: List of industry categories to consider
        - save_to_storage: Save summary to file storage (default: True)

        Returns:
        - Summary with insights, quotes, topics, and tags
        """
        parameters = parameters or {}
        summary_length = parameters.get("summary_length", "medium")
        include_quotes = parameters.get("include_quotes", True)
        include_topics = parameters.get("include_topics", True)
        include_insights = parameters.get("include_insights", True)
        industry_tags = parameters.get("industry_tags", [])
        save_to_storage = parameters.get("save_to_storage", True)

        summaries = []

        for agent_input in inputs:
            try:
                # Extract transcript text
                transcript_text, metadata = self._extract_transcript(agent_input)

                # Generate summary using LLM
                summary_data = await self._generate_summary(
                    transcript_text,
                    metadata,
                    summary_length=summary_length,
                    include_quotes=include_quotes,
                    include_topics=include_topics,
                    include_insights=include_insights,
                    industry_tags=industry_tags
                )

                # Format as markdown
                formatted_summary = self._format_as_markdown(
                    summary_data,
                    metadata
                )

                # Save to storage if requested
                file_path = None
                if save_to_storage:
                    file_path = self._save_summary(
                        formatted_summary,
                        summary_data,
                        metadata
                    )

                summaries.append({
                    "source_id": metadata.get("episode_id") or metadata.get("document_id"),
                    "title": metadata.get("title"),
                    "summary": summary_data,
                    "file_path": file_path,
                    "created_at": datetime.now().isoformat()
                })

            except Exception as e:
                logger.error(f"Error generating summary: {e}", exc_info=True)
                summaries.append({
                    "source_id": agent_input.metadata.get("episode_id"),
                    "error": str(e),
                    "status": "failed"
                })

        return AgentOutput(
            output_type="summaries",
            data={
                "summaries": summaries,
                "success_count": sum(1 for s in summaries if "error" not in s),
                "failed_count": sum(1 for s in summaries if "error" in s)
            },
            metadata={
                "summary_length": summary_length,
                "llm_provider": self.llm_client.config.provider.value,
                "llm_model": self.llm_client.config.model
            },
            processing_time_ms=0
        )

    def _extract_transcript(
        self,
        agent_input: AgentInput
    ) -> tuple[str, Dict[str, Any]]:
        """Extract transcript text and metadata from input."""
        if agent_input.input_type == "transcript":
            # Direct transcript text
            return agent_input.data, agent_input.metadata

        elif agent_input.input_type == "transcript_file":
            # Load from file
            content, metadata = self.storage.load_markdown(agent_input.data)
            # Merge with input metadata
            full_metadata = {**metadata, **agent_input.metadata}
            return content, full_metadata

        else:
            raise ValueError(f"Unsupported input type: {agent_input.input_type}")

    async def _generate_summary(
        self,
        transcript: str,
        metadata: Dict[str, Any],
        summary_length: str,
        include_quotes: bool,
        include_topics: bool,
        include_insights: bool,
        industry_tags: List[str]
    ) -> Dict[str, Any]:
        """
        Generate summary using LLM.

        Returns structured summary data.
        """
        # Build system prompt
        system_prompt = self._build_system_prompt(
            summary_length,
            include_quotes,
            include_topics,
            include_insights,
            industry_tags
        )

        # Build user prompt with transcript
        user_prompt = self._build_user_prompt(transcript, metadata)

        logger.info("Generating summary with LLM")

        # Call LLM
        response = await self.llm_client.complete_with_system(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,  # Lower temperature for more consistent summaries
            max_tokens=2000
        )

        # Parse structured response
        summary_data = self._parse_llm_response(response.content)

        # Add usage metadata
        summary_data["llm_usage"] = response.usage
        summary_data["llm_model"] = response.model

        return summary_data

    def _build_system_prompt(
        self,
        summary_length: str,
        include_quotes: bool,
        include_topics: bool,
        include_insights: bool,
        industry_tags: List[str]
    ) -> str:
        """Build system prompt for LLM."""
        length_guidance = {
            "short": "1-2 concise paragraphs",
            "medium": "3-5 well-developed paragraphs",
            "long": "detailed analysis with multiple sections"
        }

        prompt = f"""You are an expert content analyst specializing in summarizing and extracting insights from transcripts.

Your task is to analyze the provided transcript and generate a {length_guidance.get(summary_length, 'medium')} summary.

Structure your response as follows:

## Executive Summary
{length_guidance.get(summary_length, 'Provide a clear, concise summary')}

"""

        if include_insights:
            prompt += """## Key Insights
Provide 3-7 key insights or takeaways from the content. Focus on:
- Main arguments or themes
- Important data points or findings
- Actionable information
- Unique perspectives

Format as a bulleted list.

"""

        if include_topics:
            prompt += """## Topics & Themes
Identify and categorize the main topics discussed. Group related concepts.
Format as a bulleted list with brief descriptions.

"""

        if include_quotes:
            prompt += """## Notable Quotes
Extract 3-5 impactful or representative quotes from the transcript.
Format as:
- "Quote text here"
  - Context or significance

"""

        if industry_tags:
            prompt += f"""## Industry Tags
Categorize this content by relevant industries or domains. Consider these categories:
{', '.join(industry_tags)}

Select all that apply and rate relevance (high/medium/low).

"""

        prompt += """
Maintain objectivity and accuracy. Focus on substance over style.
Use clear, professional language."""

        return prompt

    def _build_user_prompt(
        self,
        transcript: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Build user prompt with transcript."""
        # Add metadata context
        context = []

        if metadata.get("title"):
            context.append(f"Title: {metadata['title']}")

        if metadata.get("podcast_name"):
            context.append(f"Source: {metadata['podcast_name']}")

        if metadata.get("publish_date"):
            context.append(f"Date: {metadata['publish_date']}")

        if metadata.get("author"):
            context.append(f"Author: {metadata['author']}")

        context_str = "\n".join(context) if context else ""

        # Truncate transcript if too long (leave room for response)
        # Most models have token limits - adjust as needed
        max_chars = 25000  # Rough approximation
        if len(transcript) > max_chars:
            transcript = transcript[:max_chars] + "\n\n[Transcript truncated for length]"
            logger.warning(f"Transcript truncated to {max_chars} characters")

        prompt = f"""Please analyze the following transcript and provide a comprehensive summary.

{context_str}

## Transcript

{transcript}

---

Please provide your analysis following the structure outlined in the system prompt."""

        return prompt

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured data.

        This does basic extraction of sections. Can be enhanced with
        more sophisticated parsing or by requesting JSON output.
        """
        summary_data = {
            "raw_response": response_text,
            "executive_summary": "",
            "key_insights": [],
            "topics": [],
            "quotes": [],
            "industry_tags": []
        }

        # Simple section extraction
        # In production, could use regex or more robust parsing
        sections = response_text.split("##")

        for section in sections:
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n", 1)
            if len(lines) < 2:
                continue

            header = lines[0].strip().lower()
            content = lines[1].strip()

            if "executive summary" in header:
                summary_data["executive_summary"] = content
            elif "key insights" in header or "insights" in header:
                summary_data["key_insights"] = self._extract_list_items(content)
            elif "topics" in header or "themes" in header:
                summary_data["topics"] = self._extract_list_items(content)
            elif "quotes" in header:
                summary_data["quotes"] = self._extract_quotes(content)
            elif "industry" in header or "tags" in header:
                summary_data["industry_tags"] = self._extract_list_items(content)

        return summary_data

    def _extract_list_items(self, content: str) -> List[str]:
        """Extract items from bulleted or numbered lists."""
        items = []
        for line in content.split("\n"):
            line = line.strip()
            # Remove bullet points, numbers, dashes
            if line.startswith(("-", "*", "•")):
                line = line[1:].strip()
            elif line and line[0].isdigit() and "." in line:
                line = line.split(".", 1)[1].strip()

            if line:
                items.append(line)

        return items

    def _extract_quotes(self, content: str) -> List[Dict[str, str]]:
        """Extract quotes with context."""
        quotes = []
        current_quote = None

        for line in content.split("\n"):
            line = line.strip()

            # Check if line contains a quote
            if '"' in line or "'" in line:
                # Extract quote text
                quote_text = line.strip('"').strip("'")
                if quote_text.startswith("-"):
                    quote_text = quote_text[1:].strip()

                current_quote = {"quote": quote_text, "context": ""}
                quotes.append(current_quote)

            elif current_quote and line.startswith("-"):
                # Context line
                current_quote["context"] = line[1:].strip()

        return quotes

    def _format_as_markdown(
        self,
        summary_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """Format summary as markdown document."""
        builder = MarkdownBuilder()

        # Add frontmatter
        builder.add_frontmatter({
            "title": metadata.get("title", "Summary"),
            "source": metadata.get("podcast_name") or metadata.get("source", "Unknown"),
            "date": metadata.get("publish_date", datetime.now().isoformat()),
            "type": "summary",
            "generated_at": datetime.now().isoformat()
        })

        # Title
        title = metadata.get("title", "Content Summary")
        builder.add_heading(title, level=1)

        # Metadata section
        builder.add_heading("Source Information", level=2)
        if metadata.get("podcast_name"):
            builder.add_paragraph(f"**Podcast:** {metadata['podcast_name']}")
        if metadata.get("author"):
            builder.add_paragraph(f"**Author:** {metadata['author']}")
        if metadata.get("publish_date"):
            builder.add_paragraph(f"**Published:** {metadata['publish_date']}")

        builder.add_horizontal_rule()

        # Executive Summary
        if summary_data.get("executive_summary"):
            builder.add_heading("Executive Summary", level=2)
            builder.add_paragraph(summary_data["executive_summary"])

        # Key Insights
        if summary_data.get("key_insights"):
            builder.add_heading("Key Insights", level=2)
            builder.add_list(summary_data["key_insights"])

        # Topics
        if summary_data.get("topics"):
            builder.add_heading("Topics & Themes", level=2)
            builder.add_list(summary_data["topics"])

        # Quotes
        if summary_data.get("quotes"):
            builder.add_heading("Notable Quotes", level=2)
            for quote in summary_data["quotes"]:
                builder.add_quote(quote["quote"])
                if quote.get("context"):
                    builder.add_paragraph(f"*{quote['context']}*")

        # Industry Tags
        if summary_data.get("industry_tags"):
            builder.add_heading("Industry Tags", level=2)
            builder.add_list(summary_data["industry_tags"])

        # Metadata footer
        builder.add_horizontal_rule()
        builder.add_paragraph(
            f"*Summary generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} "
            f"using {summary_data.get('llm_model', 'LLM')}*"
        )

        return builder.build()

    def _save_summary(
        self,
        formatted_summary: str,
        summary_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """Save summary to file storage."""
        # Generate filename
        source_id = metadata.get("episode_id") or metadata.get("document_id", "unknown")
        title = metadata.get("title", "summary")

        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))
        safe_title = safe_title.replace(" ", "_")[:50]

        filename = f"{safe_title}_{source_id}_summary"

        # Prepare metadata
        save_metadata = {
            "source_id": source_id,
            "title": metadata.get("title"),
            "source_type": metadata.get("podcast_name") and "podcast" or "document",
            "llm_model": summary_data.get("llm_model"),
            "llm_usage": summary_data.get("llm_usage"),
            "insight_count": len(summary_data.get("key_insights", [])),
            "quote_count": len(summary_data.get("quotes", [])),
        }

        file_path = self.storage.save_markdown(
            content=formatted_summary,
            filename=filename,
            content_type="summary",
            metadata=save_metadata
        )

        logger.info(f"Summary saved to {file_path}")
        return file_path

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "transcript_summarization",
            "insight_extraction",
            "topic_identification",
            "quote_extraction",
            "industry_tagging",
            "multi_llm_support"
        ]
