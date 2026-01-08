"""
Podcast Transcript Agent - Creates transcripts from podcast audio files.

This agent processes podcast episodes and generates transcripts using
an external CLI tool or transcription service.
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base_agent import BaseAgent, AgentInput, AgentOutput
from storage import FileStorage, StorageConfig, MarkdownBuilder

logger = logging.getLogger(__name__)


class PodcastTranscriptAgent(BaseAgent):
    """
    Agent that creates transcripts from podcast audio files.

    Capabilities:
    - Download audio files from URLs
    - Invoke external transcription CLI
    - Parse and format transcript output
    - Store transcripts with metadata
    - Handle multiple audio formats
    """

    def __init__(self, agent_id: str, storage_config: Optional[StorageConfig] = None):
        super().__init__(agent_id, "podcast_transcript")

        # Initialize file storage for transcripts
        self.storage = FileStorage(storage_config or StorageConfig(
            base_dir="./output",
            organize_by_date=True,
            organize_by_type=True
        ))

        # Configuration for transcript CLI (will be set from environment or config)
        self.cli_command = os.getenv("TRANSCRIPT_CLI_COMMAND", "transcript-cli")
        self.cli_args_template = os.getenv(
            "TRANSCRIPT_CLI_ARGS",
            "--input {input_file} --output {output_file}"
        )

        logger.info(f"PodcastTranscriptAgent {agent_id} initialized")

    async def process(
        self,
        inputs: List[AgentInput],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentOutput:
        """
        Process podcast episodes and create transcripts.

        Input types:
        - "episode": Podcast episode data from RSSFeedMonitorAgent
        - "audio_url": Direct audio URL to transcribe
        - "audio_file": Local audio file path

        Parameters:
        - include_timestamps: Include timestamps in transcript (default: True)
        - include_speakers: Include speaker labels if available (default: True)
        - language: Audio language code (default: auto-detect)
        - output_format: "markdown", "json", "txt" (default: "markdown")
        - save_to_storage: Save transcript to file storage (default: True)

        Returns:
        - Transcript text with metadata
        """
        parameters = parameters or {}
        include_timestamps = parameters.get("include_timestamps", True)
        include_speakers = parameters.get("include_speakers", True)
        language = parameters.get("language", "auto")
        output_format = parameters.get("output_format", "markdown")
        save_to_storage = parameters.get("save_to_storage", True)

        transcripts = []

        for agent_input in inputs:
            try:
                # Extract episode information
                episode_data = self._extract_episode_data(agent_input)

                # Generate transcript
                transcript = await self._create_transcript(
                    episode_data,
                    include_timestamps=include_timestamps,
                    include_speakers=include_speakers,
                    language=language
                )

                # Format output
                if output_format == "markdown":
                    formatted_transcript = self._format_as_markdown(
                        transcript,
                        episode_data
                    )
                else:
                    formatted_transcript = transcript

                # Save to storage if requested
                file_path = None
                if save_to_storage:
                    file_path = self._save_transcript(
                        formatted_transcript,
                        episode_data,
                        output_format
                    )

                transcripts.append({
                    "episode_id": episode_data.get("episode_id"),
                    "title": episode_data.get("title"),
                    "transcript": formatted_transcript,
                    "word_count": len(formatted_transcript.split()),
                    "file_path": file_path,
                    "created_at": datetime.now().isoformat()
                })

            except Exception as e:
                logger.error(f"Error transcribing episode: {e}")
                transcripts.append({
                    "episode_id": agent_input.metadata.get("episode_id"),
                    "error": str(e),
                    "status": "failed"
                })

        return AgentOutput(
            output_type="transcripts",
            data={
                "transcripts": transcripts,
                "success_count": sum(1 for t in transcripts if "error" not in t),
                "failed_count": sum(1 for t in transcripts if "error" in t)
            },
            metadata={
                "include_timestamps": include_timestamps,
                "include_speakers": include_speakers,
                "output_format": output_format
            },
            processing_time_ms=0
        )

    def _extract_episode_data(self, agent_input: AgentInput) -> Dict[str, Any]:
        """Extract episode data from various input formats."""
        if agent_input.input_type == "episode":
            # Full episode data from RSS monitor
            return agent_input.data

        elif agent_input.input_type == "audio_url":
            # Just a URL
            return {
                "audio_url": agent_input.data,
                "episode_id": agent_input.metadata.get("episode_id", "unknown"),
                "title": agent_input.metadata.get("title", "Unknown Episode")
            }

        elif agent_input.input_type == "audio_file":
            # Local file path
            return {
                "audio_file": agent_input.data,
                "episode_id": agent_input.metadata.get("episode_id", "unknown"),
                "title": agent_input.metadata.get("title", "Unknown Episode")
            }

        else:
            raise ValueError(f"Unsupported input type: {agent_input.input_type}")

    async def _create_transcript(
        self,
        episode_data: Dict[str, Any],
        include_timestamps: bool,
        include_speakers: bool,
        language: str
    ) -> str:
        """
        Create transcript using external CLI tool.

        This is a scaffold that will be integrated with your actual CLI tool.
        The CLI integration will be added once you share the tool details.

        Args:
            episode_data: Episode information including audio URL or file
            include_timestamps: Include timestamps in output
            include_speakers: Include speaker labels
            language: Language code for transcription

        Returns:
            Transcript text
        """
        # Get audio file (download if URL, use local if file)
        audio_file = await self._get_audio_file(episode_data)

        try:
            # Prepare output file path
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                delete=False
            ) as output_file:
                output_path = output_file.name

            # Build CLI command
            # This is a placeholder - will be replaced with actual CLI integration
            command = self._build_cli_command(
                audio_file,
                output_path,
                include_timestamps,
                include_speakers,
                language
            )

            logger.info(f"Running transcription: {command}")

            # Execute CLI command
            # NOTE: This is a placeholder that will be replaced with actual CLI
            transcript = await self._execute_cli(command, output_path)

            return transcript

        finally:
            # Cleanup temporary files
            if audio_file != episode_data.get("audio_file"):
                # Only delete if we downloaded it
                try:
                    os.unlink(audio_file)
                except Exception:
                    pass

            try:
                os.unlink(output_path)
            except Exception:
                pass

    async def _get_audio_file(self, episode_data: Dict[str, Any]) -> str:
        """
        Get audio file path (download if URL provided).

        Args:
            episode_data: Episode information

        Returns:
            Local file path to audio
        """
        # If local file provided, use it
        if "audio_file" in episode_data:
            return episode_data["audio_file"]

        # If URL provided, download it
        if "audio_url" in episode_data:
            return await self._download_audio(episode_data["audio_url"])

        raise ValueError("No audio_file or audio_url provided")

    async def _download_audio(self, url: str) -> str:
        """
        Download audio file from URL.

        Args:
            url: Audio file URL

        Returns:
            Path to downloaded file
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx not installed. Install with: pip install httpx")

        # Determine file extension from URL
        extension = Path(url).suffix or ".mp3"

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=extension,
            delete=False
        ) as temp_file:
            temp_path = temp_file.name

        logger.info(f"Downloading audio from {url}")

        async with httpx.AsyncClient() as client:
            # Stream download for large files
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                with open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

        logger.info(f"Audio downloaded to {temp_path}")
        return temp_path

    def _build_cli_command(
        self,
        input_file: str,
        output_file: str,
        include_timestamps: bool,
        include_speakers: bool,
        language: str
    ) -> str:
        """
        Build CLI command for transcription.

        This will be customized based on your actual CLI tool.
        """
        # Placeholder command building
        # Will be replaced with actual CLI integration
        args = self.cli_args_template.format(
            input_file=input_file,
            output_file=output_file
        )

        # Add optional flags based on parameters
        if include_timestamps:
            args += " --timestamps"
        if include_speakers:
            args += " --speakers"
        if language != "auto":
            args += f" --language {language}"

        return f"{self.cli_command} {args}"

    async def _execute_cli(self, command: str, output_path: str) -> str:
        """
        Execute CLI command and retrieve transcript.

        Args:
            command: CLI command to execute
            output_path: Path where transcript will be written

        Returns:
            Transcript text
        """
        # TODO: Replace this placeholder with actual CLI execution
        # For now, return placeholder text

        logger.warning(
            "CLI execution is a placeholder. "
            "Integrate with actual transcript CLI once provided."
        )

        # Placeholder: In production, this would execute the CLI:
        # process = await asyncio.create_subprocess_shell(
        #     command,
        #     stdout=asyncio.subprocess.PIPE,
        #     stderr=asyncio.subprocess.PIPE
        # )
        # stdout, stderr = await process.communicate()

        # For now, return placeholder
        return "[Transcript placeholder - CLI integration pending]"

        # In production:
        # with open(output_path, "r") as f:
        #     return f.read()

    def _format_as_markdown(
        self,
        transcript: str,
        episode_data: Dict[str, Any]
    ) -> str:
        """Format transcript as markdown with metadata."""
        builder = MarkdownBuilder()

        # Add frontmatter
        builder.add_frontmatter({
            "title": episode_data.get("title", "Unknown"),
            "podcast": episode_data.get("podcast_name", "Unknown"),
            "date": episode_data.get("publish_date", datetime.now().isoformat()),
            "duration": episode_data.get("duration"),
            "type": "transcript"
        })

        # Add title
        builder.add_heading(episode_data.get("title", "Podcast Transcript"), level=1)

        # Add metadata section
        builder.add_heading("Episode Information", level=2)
        metadata_items = [
            f"**Podcast:** {episode_data.get('podcast_name', 'Unknown')}",
            f"**Published:** {episode_data.get('publish_date', 'Unknown')}",
        ]

        if episode_data.get("author"):
            metadata_items.append(f"**Author:** {episode_data['author']}")

        if episode_data.get("duration"):
            duration_min = episode_data["duration"] // 60
            metadata_items.append(f"**Duration:** {duration_min} minutes")

        for item in metadata_items:
            builder.add_paragraph(item)

        # Add description if available
        if episode_data.get("description"):
            builder.add_heading("Description", level=2)
            builder.add_paragraph(episode_data["description"])

        # Add transcript
        builder.add_horizontal_rule()
        builder.add_heading("Transcript", level=2)
        builder.add_paragraph(transcript)

        return builder.build()

    def _save_transcript(
        self,
        transcript: str,
        episode_data: Dict[str, Any],
        output_format: str
    ) -> str:
        """Save transcript to file storage."""
        # Generate filename from episode data
        episode_id = episode_data.get("episode_id", "unknown")
        title = episode_data.get("title", "unknown")

        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_"))
        safe_title = safe_title.replace(" ", "_")[:50]  # Limit length

        filename = f"{safe_title}_{episode_id}"

        # Save with metadata
        metadata = {
            "episode_id": episode_id,
            "title": title,
            "podcast_name": episode_data.get("podcast_name"),
            "publish_date": episode_data.get("publish_date"),
            "audio_url": episode_data.get("audio_url"),
            "word_count": len(transcript.split())
        }

        file_path = self.storage.save_markdown(
            content=transcript,
            filename=filename,
            content_type="transcript",
            metadata=metadata
        )

        logger.info(f"Transcript saved to {file_path}")
        return file_path

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return [
            "audio_transcription",
            "podcast_processing",
            "transcript_formatting",
            "multi_format_output"
        ]
