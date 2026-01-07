"""
Data Ingest Agent - Handles multi-modal data ingestion
Supports text, images, JSON, and other formats
"""

import asyncio
import json
import base64
from typing import List, Dict, Any
from PIL import Image
import io
import logging

from agents.base_agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class DataIngestAgent(BaseAgent):
    """
    Ingests and preprocesses multi-modal data
    Handles text, images, JSON, and binary data
    """

    def __init__(self, agent_id: str = None, max_concurrent_tasks: int = 20):
        super().__init__(agent_id, "data_ingest", max_concurrent_tasks)

    async def process(self, inputs: List[AgentInput], parameters: Dict[str, Any]) -> AgentOutput:
        """
        Ingest and preprocess data
        Returns normalized data ready for analysis
        """
        start_time = asyncio.get_event_loop().time()

        ingested_data = []

        for inp in inputs:
            if inp.input_type == "text":
                processed = await self._process_text(inp)
            elif inp.input_type == "image":
                processed = await self._process_image(inp)
            elif inp.input_type == "json":
                processed = await self._process_json(inp)
            elif inp.input_type == "video":
                processed = await self._process_video(inp)
            else:
                processed = {"type": inp.input_type, "data": inp.data}

            ingested_data.append(processed)

        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

        return AgentOutput(
            output_type="ingested_data",
            data={
                "records": ingested_data,
                "count": len(ingested_data),
                "types": list(set(inp.input_type for inp in inputs))
            },
            metadata={
                "agent_id": self.agent_id,
                "processing_time_ms": processing_time
            },
            processing_time_ms=processing_time
        )

    async def _process_text(self, inp: AgentInput) -> Dict[str, Any]:
        """Process text input"""
        text = inp.data if isinstance(inp.data, str) else str(inp.data)

        # Basic text preprocessing
        processed = {
            "type": "text",
            "content": text,
            "length": len(text),
            "word_count": len(text.split()),
            "metadata": inp.metadata
        }

        return processed

    async def _process_image(self, inp: AgentInput) -> Dict[str, Any]:
        """Process image input"""
        # Simulate image processing
        # In production, would use PIL/OpenCV for actual processing

        image_data = inp.data

        # If data is base64, decode it
        if isinstance(image_data, str):
            try:
                image_bytes = base64.b64decode(image_data)
                img = Image.open(io.BytesIO(image_bytes))
            except Exception as e:
                logger.warning(f"Failed to decode image: {e}")
                img = None
        else:
            img = None

        processed = {
            "type": "image",
            "format": inp.metadata.get("format", "unknown"),
            "size": img.size if img else None,
            "mode": img.mode if img else None,
            "metadata": inp.metadata
        }

        return processed

    async def _process_json(self, inp: AgentInput) -> Dict[str, Any]:
        """Process JSON input"""
        if isinstance(inp.data, str):
            try:
                data = json.loads(inp.data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                data = {"error": "Invalid JSON"}
        else:
            data = inp.data

        processed = {
            "type": "json",
            "data": data,
            "keys": list(data.keys()) if isinstance(data, dict) else [],
            "metadata": inp.metadata
        }

        return processed

    async def _process_video(self, inp: AgentInput) -> Dict[str, Any]:
        """Process video input (metadata extraction)"""
        # In production, would use OpenCV or similar for frame extraction

        processed = {
            "type": "video",
            "format": inp.metadata.get("format", "unknown"),
            "duration_sec": inp.metadata.get("duration", 0),
            "fps": inp.metadata.get("fps", 30),
            "resolution": inp.metadata.get("resolution", "unknown"),
            "metadata": inp.metadata
        }

        return processed
