"""
File storage utilities for agent outputs.
Supports markdown files with metadata and organized directory structure.
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Configuration for file storage."""
    base_dir: str = "./output"
    organize_by_date: bool = True  # Create date-based subdirectories
    organize_by_type: bool = True  # Create type-based subdirectories
    include_metadata: bool = True  # Store JSON metadata alongside markdown
    timestamp_format: str = "%Y-%m-%d_%H-%M-%S"


class FileStorage:
    """
    File storage manager for agent outputs.
    Creates organized directory structures and handles file writing.
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        """
        Initialize file storage with configuration.

        Args:
            config: Storage configuration (uses defaults if not provided)
        """
        self.config = config or StorageConfig()
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Create base directory if it doesn't exist."""
        Path(self.config.base_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage initialized at: {self.config.base_dir}")

    def _get_storage_path(
        self,
        filename: str,
        content_type: str,
        timestamp: Optional[datetime] = None
    ) -> Path:
        """
        Generate organized file path based on configuration.

        Args:
            filename: Base filename
            content_type: Type of content (e.g., "transcript", "summary", "report")
            timestamp: Optional timestamp (uses current time if not provided)

        Returns:
            Full path for the file
        """
        path_parts = [self.config.base_dir]

        # Add type-based subdirectory
        if self.config.organize_by_type:
            path_parts.append(content_type)

        # Add date-based subdirectory
        if self.config.organize_by_date:
            ts = timestamp or datetime.now()
            path_parts.append(ts.strftime("%Y-%m-%d"))

        # Create full path
        full_path = Path(*path_parts)
        full_path.mkdir(parents=True, exist_ok=True)

        return full_path / filename

    def save_markdown(
        self,
        content: str,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save content as markdown file with optional metadata.

        Args:
            content: Markdown content to save
            filename: Filename (without extension)
            content_type: Type of content for organization
            metadata: Optional metadata to save alongside
            timestamp: Optional timestamp for organization

        Returns:
            Absolute path to saved file

        Example:
            >>> storage = FileStorage()
            >>> path = storage.save_markdown(
            ...     content="# Summary\nThis is a summary",
            ...     filename="episode_001",
            ...     content_type="summary",
            ...     metadata={"source": "podcast", "duration": 3600}
            ... )
        """
        # Ensure .md extension
        if not filename.endswith(".md"):
            filename = f"{filename}.md"

        file_path = self._get_storage_path(filename, content_type, timestamp)

        # Write markdown file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Saved markdown file: {file_path}")

        # Save metadata if requested
        if metadata and self.config.include_metadata:
            self._save_metadata(file_path, metadata, timestamp)

        return str(file_path.absolute())

    def _save_metadata(
        self,
        markdown_path: Path,
        metadata: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ):
        """
        Save metadata as JSON file alongside markdown.

        Args:
            markdown_path: Path to the markdown file
            metadata: Metadata to save
            timestamp: Optional timestamp
        """
        # Create metadata file path (same name, .json extension)
        metadata_path = markdown_path.with_suffix(".json")

        # Add automatic metadata
        full_metadata = {
            "created_at": (timestamp or datetime.now()).isoformat(),
            "markdown_file": markdown_path.name,
            **metadata
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(full_metadata, f, indent=2)

        logger.info(f"Saved metadata file: {metadata_path}")

    def load_markdown(self, file_path: str) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Load markdown file and its metadata if available.

        Args:
            file_path: Path to markdown file

        Returns:
            Tuple of (content, metadata)
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read markdown content
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to load metadata
        metadata = None
        metadata_path = path.with_suffix(".json")
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        return content, metadata

    def list_files(
        self,
        content_type: Optional[str] = None,
        date: Optional[str] = None
    ) -> list[str]:
        """
        List stored files, optionally filtered by type and date.

        Args:
            content_type: Filter by content type
            date: Filter by date (YYYY-MM-DD format)

        Returns:
            List of file paths
        """
        base_path = Path(self.config.base_dir)

        if content_type:
            base_path = base_path / content_type

        if date and self.config.organize_by_date:
            base_path = base_path / date

        if not base_path.exists():
            return []

        # Find all markdown files
        return [str(p) for p in base_path.rglob("*.md")]

    def get_latest(self, content_type: str) -> Optional[str]:
        """
        Get the most recently created file of a specific type.

        Args:
            content_type: Type of content to search for

        Returns:
            Path to latest file, or None if no files found
        """
        files = self.list_files(content_type)

        if not files:
            return None

        # Sort by modification time
        latest = max(files, key=lambda f: os.path.getmtime(f))
        return latest


class MarkdownBuilder:
    """
    Helper class for building well-formatted markdown documents.
    """

    def __init__(self):
        self.sections = []

    def add_frontmatter(self, metadata: Dict[str, Any]) -> "MarkdownBuilder":
        """Add YAML frontmatter to the document."""
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, str):
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: {json.dumps(value)}")
        lines.append("---")
        lines.append("")  # Blank line after frontmatter

        self.sections.insert(0, "\n".join(lines))
        return self

    def add_heading(self, text: str, level: int = 1) -> "MarkdownBuilder":
        """Add a heading."""
        self.sections.append(f"{'#' * level} {text}\n")
        return self

    def add_paragraph(self, text: str) -> "MarkdownBuilder":
        """Add a paragraph."""
        self.sections.append(f"{text}\n")
        return self

    def add_list(self, items: list[str], ordered: bool = False) -> "MarkdownBuilder":
        """Add a list (bulleted or numbered)."""
        lines = []
        for i, item in enumerate(items, 1):
            prefix = f"{i}." if ordered else "-"
            lines.append(f"{prefix} {item}")
        self.sections.append("\n".join(lines) + "\n")
        return self

    def add_code_block(self, code: str, language: str = "") -> "MarkdownBuilder":
        """Add a code block."""
        self.sections.append(f"```{language}\n{code}\n```\n")
        return self

    def add_quote(self, text: str) -> "MarkdownBuilder":
        """Add a blockquote."""
        lines = [f"> {line}" for line in text.split("\n")]
        self.sections.append("\n".join(lines) + "\n")
        return self

    def add_horizontal_rule(self) -> "MarkdownBuilder":
        """Add a horizontal rule."""
        self.sections.append("---\n")
        return self

    def add_table(self, headers: list[str], rows: list[list[str]]) -> "MarkdownBuilder":
        """Add a table."""
        lines = []

        # Header row
        lines.append("| " + " | ".join(headers) + " |")

        # Separator
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Data rows
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")

        self.sections.append("\n".join(lines) + "\n")
        return self

    def add_custom(self, markdown: str) -> "MarkdownBuilder":
        """Add custom markdown content."""
        self.sections.append(markdown + "\n")
        return self

    def build(self) -> str:
        """Build the final markdown document."""
        return "\n".join(self.sections)
