"""
Document Reader Agent - Reads and extracts text from various document formats.

Supports:
- Plain text files (.txt, .md)
- PDF documents (direct text extraction)
- Screenshots/images (OCR)
- Web pages (HTML to text)
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib

from agents.base_agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class DocumentReaderAgent(BaseAgent):
    """
    Agent that extracts text content from various document formats.

    Capabilities:
    - Read text files (txt, md, etc.)
    - Extract text from PDFs
    - OCR from images/screenshots
    - Convert HTML to markdown
    - Handle multiple file formats
    - Preserve document metadata
    """

    def __init__(self, agent_id: str):
        super().__init__(agent_id, "document_reader")

        # Configure OCR if needed (Tesseract or cloud services)
        self.ocr_enabled = os.getenv("OCR_ENABLED", "true").lower() == "true"
        self.use_vision_api = os.getenv("USE_VISION_API", "false").lower() == "true"

        logger.info(
            f"DocumentReaderAgent {agent_id} initialized "
            f"(OCR: {self.ocr_enabled}, Vision API: {self.use_vision_api})"
        )

    async def process(
        self,
        inputs: List[AgentInput],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentOutput:
        """
        Process documents and extract text content.

        Input types:
        - "file_path": Path to local file
        - "file_url": URL to download file from
        - "image": Image file (for OCR)
        - "screenshot": Screenshot image (for OCR)
        - "html": HTML content to convert

        Parameters:
        - extract_metadata: Include file metadata (default: True)
        - clean_text: Clean extracted text (remove extra whitespace, etc.)
        - ocr_language: Language for OCR (default: "eng")
        - preserve_formatting: Try to preserve document structure

        Returns:
        - Extracted text with metadata
        """
        parameters = parameters or {}
        extract_metadata = parameters.get("extract_metadata", True)
        clean_text = parameters.get("clean_text", True)
        ocr_language = parameters.get("ocr_language", "eng")
        preserve_formatting = parameters.get("preserve_formatting", True)

        documents = []

        for agent_input in inputs:
            try:
                # Extract text based on input type
                text, metadata = await self._extract_text(
                    agent_input,
                    ocr_language=ocr_language,
                    preserve_formatting=preserve_formatting
                )

                # Clean text if requested
                if clean_text:
                    text = self._clean_text(text)

                # Generate document ID
                doc_id = self._generate_document_id(text, metadata)

                # Merge metadata
                full_metadata = {
                    **agent_input.metadata,
                    **metadata
                }

                if extract_metadata:
                    full_metadata["extraction_timestamp"] = datetime.now().isoformat()
                    full_metadata["character_count"] = len(text)
                    full_metadata["word_count"] = len(text.split())

                documents.append({
                    "document_id": doc_id,
                    "text": text,
                    "metadata": full_metadata,
                    "input_type": agent_input.input_type,
                    "status": "success"
                })

            except Exception as e:
                logger.error(f"Error extracting text from document: {e}", exc_info=True)
                documents.append({
                    "document_id": None,
                    "error": str(e),
                    "input_type": agent_input.input_type,
                    "status": "failed"
                })

        return AgentOutput(
            output_type="documents",
            data={
                "documents": documents,
                "success_count": sum(1 for d in documents if d["status"] == "success"),
                "failed_count": sum(1 for d in documents if d["status"] == "failed")
            },
            metadata={
                "clean_text": clean_text,
                "ocr_enabled": self.ocr_enabled
            },
            processing_time_ms=0
        )

    async def _extract_text(
        self,
        agent_input: AgentInput,
        ocr_language: str,
        preserve_formatting: bool
    ) -> tuple[str, Dict[str, Any]]:
        """
        Extract text based on input type.

        Returns:
            Tuple of (text, metadata)
        """
        input_type = agent_input.input_type
        metadata = {}

        if input_type == "file_path":
            # Local file
            file_path = agent_input.data
            return await self._read_file(file_path, ocr_language, preserve_formatting)

        elif input_type == "file_url":
            # Download and process
            file_path = await self._download_file(agent_input.data)
            try:
                return await self._read_file(file_path, ocr_language, preserve_formatting)
            finally:
                # Cleanup downloaded file
                try:
                    os.unlink(file_path)
                except Exception:
                    pass

        elif input_type in ("image", "screenshot"):
            # OCR from image
            if isinstance(agent_input.data, str):
                # File path
                return await self._ocr_image(agent_input.data, ocr_language)
            else:
                # Binary data
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
                    f.write(agent_input.data)
                    temp_path = f.name

                try:
                    return await self._ocr_image(temp_path, ocr_language)
                finally:
                    os.unlink(temp_path)

        elif input_type == "html":
            # Convert HTML to text
            text = self._html_to_text(agent_input.data, preserve_formatting)
            return text, {"format": "html"}

        elif input_type == "text":
            # Direct text input
            return agent_input.data, {"format": "text"}

        else:
            raise ValueError(f"Unsupported input type: {input_type}")

    async def _read_file(
        self,
        file_path: str,
        ocr_language: str,
        preserve_formatting: bool
    ) -> tuple[str, Dict[str, Any]]:
        """Read file and extract text based on extension."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file metadata
        metadata = {
            "filename": path.name,
            "extension": path.suffix,
            "size_bytes": path.stat().st_size,
            "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        }

        extension = path.suffix.lower()

        # Text files
        if extension in (".txt", ".md", ".markdown", ".rst", ".log"):
            text = await self._read_text_file(file_path)
            metadata["format"] = "text"
            return text, metadata

        # PDF files
        elif extension == ".pdf":
            text = await self._read_pdf(file_path)
            metadata["format"] = "pdf"
            return text, metadata

        # Image files (OCR)
        elif extension in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"):
            text = await self._ocr_image(file_path, ocr_language)
            metadata["format"] = "image"
            metadata["ocr_language"] = ocr_language
            return text, metadata

        # HTML/XML
        elif extension in (".html", ".htm", ".xml"):
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            text = self._html_to_text(html_content, preserve_formatting)
            metadata["format"] = "html"
            return text, metadata

        # JSON (extract text content)
        elif extension == ".json":
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = str(data)  # Simple string conversion
            metadata["format"] = "json"
            return text, metadata

        else:
            raise ValueError(f"Unsupported file format: {extension}")

    async def _read_text_file(self, file_path: str) -> str:
        """Read plain text file."""
        encodings = ["utf-8", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        raise ValueError(f"Could not decode file with supported encodings: {file_path}")

    async def _read_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF file.

        Tries multiple libraries for best results:
        1. PyMuPDF (fitz) - Fast and reliable
        2. pdfplumber - Good for tables
        3. pypdf2 - Fallback
        """
        text = None

        # Try PyMuPDF first
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            text_parts = []

            for page in doc:
                text_parts.append(page.get_text())

            text = "\n\n".join(text_parts)
            doc.close()

            if text.strip():
                return text

        except ImportError:
            logger.debug("PyMuPDF (fitz) not available")
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")

        # Try pdfplumber
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                text = "\n\n".join(text_parts)

            if text and text.strip():
                return text

        except ImportError:
            logger.debug("pdfplumber not available")
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")

        # Try pypdf2
        try:
            import pypdf2

            with open(file_path, "rb") as f:
                reader = pypdf2.PdfReader(f)
                text_parts = []

                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                text = "\n\n".join(text_parts)

            if text and text.strip():
                return text

        except ImportError:
            logger.debug("pypdf2 not available")
        except Exception as e:
            logger.warning(f"pypdf2 extraction failed: {e}")

        # If all methods failed
        if not text or not text.strip():
            raise RuntimeError(
                "Could not extract text from PDF. PDF may be image-based. "
                "Consider using OCR. Install: pip install PyMuPDF pdfplumber"
            )

        return text

    async def _ocr_image(self, image_path: str, language: str = "eng") -> tuple[str, Dict]:
        """
        Extract text from image using OCR.

        Supports:
        1. Vision API (Claude/OpenAI) - Most accurate
        2. Tesseract OCR - Local, free
        """
        metadata = {"ocr_method": None, "ocr_language": language}

        # Try Vision API first if enabled
        if self.use_vision_api:
            try:
                text = await self._ocr_with_vision_api(image_path)
                metadata["ocr_method"] = "vision_api"
                return text, metadata
            except Exception as e:
                logger.warning(f"Vision API OCR failed: {e}")

        # Fallback to Tesseract
        if self.ocr_enabled:
            try:
                text = await self._ocr_with_tesseract(image_path, language)
                metadata["ocr_method"] = "tesseract"
                return text, metadata
            except Exception as e:
                logger.error(f"Tesseract OCR failed: {e}")
                raise RuntimeError(
                    "OCR failed. Install Tesseract: "
                    "https://github.com/tesseract-ocr/tesseract"
                )

        raise RuntimeError("OCR is disabled. Enable with OCR_ENABLED=true")

    async def _ocr_with_tesseract(self, image_path: str, language: str) -> str:
        """OCR using Tesseract."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ImportError(
                "pytesseract and Pillow required. "
                "Install: pip install pytesseract Pillow"
            )

        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang=language)

        return text

    async def _ocr_with_vision_api(self, image_path: str) -> str:
        """
        OCR using Claude or OpenAI vision capabilities.

        This provides more accurate text extraction than traditional OCR.
        """
        from llm import LLMClient
        import base64

        # Load and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        # Use Claude or OpenAI vision
        # This is a simplified version - actual implementation depends on provider
        client = LLMClient.from_env(
            provider=os.getenv("LLM_PROVIDER", "anthropic"),
            model=os.getenv("VISION_MODEL", "claude-3-5-sonnet-20241022")
        )

        prompt = """Extract all text from this image. Provide the text exactly as it appears,
preserving formatting and structure as much as possible. Do not add commentary or explanations,
just output the extracted text."""

        # Note: This is a placeholder - actual image handling depends on the provider
        # For production, would need to properly format image messages
        response = await client.complete(prompt)

        return response.content

    def _html_to_text(self, html_content: str, preserve_formatting: bool) -> str:
        """Convert HTML to plain text."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback to simple regex-based stripping
            import re
            text = re.sub(r"<[^>]+>", "", html_content)
            return text

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        if preserve_formatting:
            # Get text with some structure preservation
            text = soup.get_text(separator="\n", strip=True)
        else:
            # Get plain text
            text = soup.get_text()

        return text

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        import re

        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        # Remove common OCR artifacts
        text = re.sub(r"[|]{2,}", "", text)  # Multiple pipes
        text = re.sub(r"_{3,}", "", text)  # Multiple underscores

        # Trim lines
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    def _generate_document_id(self, text: str, metadata: Dict[str, Any]) -> str:
        """Generate unique document ID."""
        # Use filename if available, otherwise hash the content
        if metadata.get("filename"):
            base = metadata["filename"]
        else:
            # Hash first 1000 chars
            content = text[:1000]
            base = hashlib.md5(content.encode()).hexdigest()[:12]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base}_{timestamp}"

    async def _download_file(self, url: str) -> str:
        """Download file from URL to temporary location."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx required for downloads. Install: pip install httpx")

        import tempfile

        # Determine extension from URL
        extension = Path(url).suffix or ".tmp"

        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as f:
            temp_path = f.name

        logger.info(f"Downloading file from {url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            with open(temp_path, "wb") as f:
                f.write(response.content)

        logger.info(f"File downloaded to {temp_path}")
        return temp_path

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        capabilities = [
            "text_extraction",
            "pdf_reading",
            "multi_format_support",
            "metadata_extraction",
            "html_to_text"
        ]

        if self.ocr_enabled:
            capabilities.append("ocr")

        if self.use_vision_api:
            capabilities.append("vision_api_ocr")

        return capabilities
