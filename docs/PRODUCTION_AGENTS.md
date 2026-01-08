# Production-Ready Agents

This document describes the production-ready agents that replace the original placeholder implementations.

## Overview

The orchestrator now includes five new production-ready agents designed for content intelligence workflows:

1. **RSSFeedMonitorAgent** - Monitors RSS feeds for new podcast episodes
2. **PodcastTranscriptAgent** - Creates transcripts from podcast audio
3. **TranscriptSummaryAgent** - Generates summaries and insights using LLMs
4. **DocumentReaderAgent** - Extracts text from various document formats
5. **IndustrySynthesisAgent** - Synthesizes cross-source intelligence reports

These agents work together to create automated content intelligence pipelines.

---

## Agent Descriptions

### 1. RSSFeedMonitorAgent

**Purpose**: Monitor RSS feeds for new podcast episodes and extract metadata.

**Capabilities**:
- Poll RSS feeds on configurable schedules
- Parse podcast metadata (title, description, publish date, duration)
- Extract audio URLs for transcription
- Track processed episodes to avoid duplicates
- Support multiple feeds with individual configurations
- Filter episodes by date range

**Input Types**:
- `feed_config`: JSON configuration with RSS feed URLs and settings
- `check_request`: Request to check specific feeds

**Parameters**:
- `lookback_days` (int, default: 7): How many days back to check for episodes
- `force_refresh` (bool, default: False): Ignore last check time
- `feed_urls` (list, optional): Specific feeds to check

**Output**:
```json
{
  "episodes": [
    {
      "episode_id": "...",
      "title": "...",
      "description": "...",
      "audio_url": "...",
      "publish_date": "...",
      "duration": 3600,
      "podcast_name": "...",
      "author": "..."
    }
  ],
  "feeds_checked": 5,
  "new_count": 12
}
```

**Environment Variables**:
- None (configuration via input data)

**Dependencies**:
- `feedparser`: RSS/Atom feed parsing

**Example**:
```python
agent = RSSFeedMonitorAgent("rss-monitor-001")

feed_config = {
    "feeds": [
        {
            "feed_url": "https://example.com/podcast/feed.xml",
            "feed_name": "Tech Talks",
            "enabled": True,
            "check_frequency_hours": 24,
            "tags": ["technology"]
        }
    ]
}

result = await agent.process([AgentInput(..., data=feed_config)])
```

---

### 2. PodcastTranscriptAgent

**Purpose**: Create transcripts from podcast audio files.

**Capabilities**:
- Download audio from URLs
- Integrate with external transcription CLI tools
- Support multiple audio formats
- Format transcripts as markdown with metadata
- Include timestamps and speaker labels (if available)
- Store transcripts locally

**Input Types**:
- `episode`: Full episode data from RSSFeedMonitorAgent
- `audio_url`: Direct audio URL
- `audio_file`: Local audio file path

**Parameters**:
- `include_timestamps` (bool, default: True): Include timestamps in transcript
- `include_speakers` (bool, default: True): Include speaker labels
- `language` (str, default: "auto"): Audio language code
- `output_format` (str, default: "markdown"): Output format
- `save_to_storage` (bool, default: True): Save to file storage

**Output**:
```json
{
  "transcripts": [
    {
      "episode_id": "...",
      "title": "...",
      "transcript": "...",
      "word_count": 5000,
      "file_path": "/output/transcript/...",
      "created_at": "..."
    }
  ],
  "success_count": 1,
  "failed_count": 0
}
```

**Environment Variables**:
- `TRANSCRIPT_CLI_COMMAND`: Command for your transcript CLI tool
- `TRANSCRIPT_CLI_ARGS`: Argument template for CLI

**Dependencies**:
- `httpx`: For downloading audio files
- External transcription CLI (user-provided)

**Integration Notes**:
- The agent provides a scaffold for CLI integration
- You'll need to configure your specific transcription tool
- Supports any CLI that takes audio input and produces text output

**Example**:
```python
agent = PodcastTranscriptAgent("transcript-001")

result = await agent.process([
    AgentInput(
        input_type="episode",
        data=episode_data
    )
])
```

---

### 3. TranscriptSummaryAgent

**Purpose**: Generate summaries and extract insights from transcripts using LLMs.

**Capabilities**:
- Generate executive summaries (short, medium, or long)
- Extract key insights and takeaways
- Identify and categorize topics
- Extract notable quotes
- Tag content by industry/domain
- Support multiple LLM providers (OpenAI, Anthropic)
- Store summaries as markdown

**Input Types**:
- `transcript`: Full transcript text
- `transcript_file`: Path to transcript file

**Parameters**:
- `summary_length` (str, default: "medium"): "short", "medium", or "long"
- `include_quotes` (bool, default: True): Extract notable quotes
- `include_topics` (bool, default: True): Identify topics
- `include_insights` (bool, default: True): Extract key insights
- `industry_tags` (list): List of industry categories to consider
- `save_to_storage` (bool, default: True): Save summary to storage

**Output**:
```json
{
  "summaries": [
    {
      "source_id": "...",
      "title": "...",
      "summary": {
        "executive_summary": "...",
        "key_insights": ["...", "..."],
        "topics": ["...", "..."],
        "quotes": [{"quote": "...", "context": "..."}],
        "industry_tags": ["...", "..."]
      },
      "file_path": "/output/summary/...",
      "created_at": "..."
    }
  ]
}
```

**Environment Variables**:
- `LLM_PROVIDER`: "openai" or "anthropic" (default: "openai")
- `LLM_MODEL`: Specific model name (optional, uses defaults)
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key

**Dependencies**:
- `openai`: OpenAI Python SDK
- `anthropic`: Anthropic Python SDK

**LLM Configuration**:
```python
from llm import LLMConfig, LLMProvider

# Option 1: Explicit configuration
config = LLMConfig(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-5-sonnet-20241022",
    temperature=0.5,
    max_tokens=2000
)
agent = TranscriptSummaryAgent("summary-001", llm_config=config)

# Option 2: Environment-based
# Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY
agent = TranscriptSummaryAgent("summary-001")
```

---

### 4. DocumentReaderAgent

**Purpose**: Extract text from various document formats.

**Capabilities**:
- Read plain text files (.txt, .md, .log, etc.)
- Extract text from PDFs (using multiple libraries for best results)
- OCR from images/screenshots (Tesseract or Vision API)
- Convert HTML to text
- Handle multiple file formats
- Preserve document metadata
- Clean and normalize extracted text

**Input Types**:
- `file_path`: Path to local file
- `file_url`: URL to download file from
- `image`: Image file for OCR
- `screenshot`: Screenshot image for OCR
- `html`: HTML content to convert

**Parameters**:
- `extract_metadata` (bool, default: True): Include file metadata
- `clean_text` (bool, default: True): Clean extracted text
- `ocr_language` (str, default: "eng"): Language for OCR
- `preserve_formatting` (bool, default: True): Preserve document structure

**Output**:
```json
{
  "documents": [
    {
      "document_id": "...",
      "text": "...",
      "metadata": {
        "filename": "...",
        "extension": ".pdf",
        "size_bytes": 125000,
        "format": "pdf",
        "word_count": 5000,
        "character_count": 30000,
        "extraction_timestamp": "..."
      },
      "input_type": "file_path",
      "status": "success"
    }
  ]
}
```

**Environment Variables**:
- `OCR_ENABLED` (default: "true"): Enable OCR processing
- `USE_VISION_API` (default: "false"): Use LLM vision API for OCR

**Dependencies**:
- `PyMuPDF` (fitz): Primary PDF extraction
- `pdfplumber`: Alternative PDF extraction
- `beautifulsoup4`: HTML parsing
- `pytesseract` (optional): Tesseract OCR
- `Pillow`: Image processing

**Supported Formats**:
- **Text**: .txt, .md, .markdown, .rst, .log
- **PDF**: .pdf
- **Images**: .png, .jpg, .jpeg, .bmp, .tiff, .gif
- **Web**: .html, .htm, .xml
- **Data**: .json

**Example**:
```python
agent = DocumentReaderAgent("doc-reader-001")

result = await agent.process([
    AgentInput(
        input_type="file_path",
        data="/path/to/document.pdf"
    )
])
```

---

### 5. IndustrySynthesisAgent

**Purpose**: Synthesize intelligence from multiple summaries to identify trends and patterns.

**Capabilities**:
- Aggregate insights from multiple sources
- Identify cross-cutting themes
- Analyze trends over time
- Group by industry/topic
- Generate executive intelligence reports
- Frequency analysis of concepts
- Comparative analysis across sources
- Support daily, weekly, and monthly reports

**Input Types**:
- `summary`: Individual summary data
- `summary_file`: Path to summary file
- `summaries_batch`: List of summaries

**Parameters**:
- `report_type` (str, default: "weekly"): "daily", "weekly", or "monthly"
- `industries` (list): Industries to focus on
- `include_trends` (bool, default: True): Include trend analysis
- `include_topics` (bool, default: True): Include topic frequency
- `include_comparison` (bool, default: True): Compare sources
- `min_frequency` (int, default: 2): Minimum mentions for topic inclusion
- `save_to_storage` (bool, default: True): Save report

**Output**:
```json
{
  "report": {
    "executive_summary": "...",
    "key_themes": "...",
    "emerging_trends": "...",
    "industry_insights": "...",
    "cross_cutting": "...",
    "outlook": "..."
  },
  "analysis": {
    "total_summaries": 25,
    "date_range": {...},
    "topics": {
      "total_unique": 150,
      "top_topics": {...}
    },
    "trends": {...},
    "industries": {...}
  },
  "file_path": "/output/synthesis_report/...",
  "summary_count": 25
}
```

**Environment Variables**:
- `LLM_PROVIDER`: "openai" or "anthropic"
- `LLM_MODEL`: Specific model name
- API keys (same as TranscriptSummaryAgent)

**Dependencies**:
- `openai` or `anthropic`: LLM providers

**Example**:
```python
agent = IndustrySynthesisAgent("synthesis-001")

result = await agent.process(
    [AgentInput(input_type="summary", data=summary) for summary in summaries],
    parameters={
        "report_type": "weekly",
        "industries": ["Technology", "Finance", "Healthcare"]
    }
)
```

---

## Workflows

### Podcast Intelligence Workflow

Complete pipeline for podcast content intelligence:

```
RSSFeedMonitorAgent
  ↓ (new episodes)
PodcastTranscriptAgent
  ↓ (transcripts)
TranscriptSummaryAgent
  ↓ (summaries)
IndustrySynthesisAgent
  ↓ (intelligence report)
```

**Task Type**: `podcast_intelligence`

**Execution Mode**: SEQUENTIAL

**Example**:
```python
task_def = TaskDefinition(
    task_id="podcast-intel-001",
    task_type="podcast_intelligence",
    inputs=[...],
    execution_mode=ExecutionMode.SEQUENTIAL,
    priority=5,
    timeout_ms=300000
)
```

### Document Intelligence Workflow

Complete pipeline for document content intelligence:

```
DocumentReaderAgent
  ↓ (extracted text)
TranscriptSummaryAgent
  ↓ (summaries)
IndustrySynthesisAgent
  ↓ (intelligence report)
```

**Task Type**: `document_intelligence`

**Execution Mode**: SEQUENTIAL or HYBRID (for parallel document processing)

**Example**:
```python
task_def = TaskDefinition(
    task_id="doc-intel-001",
    task_type="document_intelligence",
    inputs=[...],
    execution_mode=ExecutionMode.HYBRID,  # Parallel doc reading + sequential summarization
    priority=5,
    timeout_ms=600000
)
```

---

## Setup & Configuration

### 1. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# For PDF processing
pip install PyMuPDF pdfplumber

# For OCR (optional)
pip install pytesseract
# Also install Tesseract: https://github.com/tesseract-ocr/tesseract

# For HTML parsing
pip install beautifulsoup4 lxml
```

### 2. Configure Environment Variables

Create a `.env` file or set environment variables:

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM Provider
LLM_PROVIDER=anthropic  # or "openai"
LLM_MODEL=claude-3-5-sonnet-20241022  # optional

# API Keys
ANTHROPIC_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here

# Transcript CLI (configure when ready)
TRANSCRIPT_CLI_COMMAND=/path/to/your/transcript-cli
TRANSCRIPT_CLI_ARGS=--input {input_file} --output {output_file}

# OCR Configuration
OCR_ENABLED=true
USE_VISION_API=false  # Set to true to use Claude/GPT vision for OCR

# Logging
LOG_LEVEL=INFO
```

### 3. Configure RSS Feeds

RSS feeds are configured via input data. Create a feeds configuration file:

```json
{
  "feeds": [
    {
      "feed_url": "https://example.com/podcast1/feed.xml",
      "feed_name": "Tech Podcast",
      "enabled": true,
      "check_frequency_hours": 24,
      "tags": ["technology", "business"]
    },
    {
      "feed_url": "https://example.com/podcast2/feed.xml",
      "feed_name": "Industry News",
      "enabled": true,
      "check_frequency_hours": 24,
      "tags": ["industry", "news"]
    }
  ]
}
```

### 4. Start Agents

Start individual agents with specific types:

```bash
# RSS Feed Monitor
AGENT_TYPE=rss_feed_monitor python main_agent.py

# Podcast Transcript
AGENT_TYPE=podcast_transcript python main_agent.py

# Transcript Summary
AGENT_TYPE=transcript_summary python main_agent.py

# Document Reader
AGENT_TYPE=document_reader python main_agent.py

# Industry Synthesis
AGENT_TYPE=industry_synthesis python main_agent.py
```

### 5. Start Orchestrator

```bash
python main_orchestrator.py
```

---

## File Storage

All outputs are stored in organized directory structures:

```
output/
├── transcript/
│   ├── 2024-01-15/
│   │   ├── episode_001.md
│   │   ├── episode_001.json (metadata)
│   │   └── ...
│   └── 2024-01-16/
├── summary/
│   ├── 2024-01-15/
│   │   ├── episode_001_summary.md
│   │   ├── episode_001_summary.json
│   │   └── ...
│   └── 2024-01-16/
└── synthesis_report/
    ├── 2024-01-15/
    │   ├── weekly_synthesis_2024-01-15.md
    │   ├── weekly_synthesis_2024-01-15.json
    │   └── ...
    └── 2024-01-16/
```

Configure storage location via `StorageConfig`:

```python
from storage import FileStorage, StorageConfig

config = StorageConfig(
    base_dir="./output",
    organize_by_date=True,
    organize_by_type=True,
    include_metadata=True
)

storage = FileStorage(config)
```

---

## LLM Provider Configuration

### Switching Providers

The system supports multiple LLM providers through a unified interface.

**Option 1: Environment Variables**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key
```

**Option 2: Explicit Configuration**
```python
from llm import LLMConfig, LLMProvider

config = LLMConfig(
    provider=LLMProvider.ANTHROPIC,
    model="claude-3-5-sonnet-20241022",
    temperature=0.7,
    max_tokens=4000
)
```

### Supported Providers

**OpenAI**:
- Models: gpt-4, gpt-4-turbo, gpt-3.5-turbo
- Best for: Fast iteration, cost-effective

**Anthropic Claude**:
- Models: claude-3-5-sonnet, claude-3-opus, claude-3-haiku
- Best for: Long-form content, nuanced analysis

### Adding Custom Providers

```python
from llm import BaseLLMProvider, LLMProviderFactory, LLMProvider

class CustomProvider(BaseLLMProvider):
    async def complete(self, messages, **kwargs):
        # Your implementation
        pass

# Register
LLMProviderFactory.register_provider(
    LLMProvider.CUSTOM,
    CustomProvider
)
```

---

## Scheduling

For automated daily/weekly execution, use a scheduler:

### Option 1: APScheduler (Python)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Daily summary generation
scheduler.add_job(
    run_daily_summaries,
    'cron',
    hour=8,
    minute=0
)

# Weekly synthesis reports
scheduler.add_job(
    run_weekly_synthesis,
    'cron',
    day_of_week='mon',
    hour=9,
    minute=0
)

scheduler.start()
```

### Option 2: System Cron

```cron
# Check feeds daily at 8 AM
0 8 * * * cd /path/to/orchestrator && python -m scripts.daily_podcast_check

# Weekly synthesis every Monday at 9 AM
0 9 * * 1 cd /path/to/orchestrator && python -m scripts.weekly_synthesis
```

### Option 3: Kubernetes CronJob

See `k8s/cronjob-*.yaml` for examples.

---

## Troubleshooting

### Common Issues

**1. RSS Feed Parsing Errors**
- Check feed URL is valid and accessible
- Verify feedparser is installed: `pip install feedparser`
- Check feed format (RSS 2.0 or Atom)

**2. PDF Extraction Failures**
- Install multiple PDF libraries for fallback support
- For image-based PDFs, enable OCR
- Check file permissions

**3. OCR Not Working**
- Install Tesseract: `brew install tesseract` (Mac) or `apt-get install tesseract-ocr` (Linux)
- Install pytesseract: `pip install pytesseract`
- Or enable Vision API: `USE_VISION_API=true`

**4. LLM API Errors**
- Verify API keys are set correctly
- Check API quotas and rate limits
- Ensure model names are correct

**5. Storage Permission Errors**
- Check write permissions in output directory
- Ensure parent directories exist

---

## Performance Considerations

### Parallel Processing

For large batches of documents, use HYBRID execution mode:

```python
task_def = TaskDefinition(
    ...
    execution_mode=ExecutionMode.HYBRID,
    ...
)
```

This processes documents in parallel, then summarizes sequentially.

### Token Limits

When summarizing very long transcripts:
- Increase `max_tokens` in LLM config
- Or split transcript into chunks
- Monitor token usage in response metadata

### Rate Limiting

Handle API rate limits:
- Configure retry logic (built-in with tenacity)
- Add delays between requests
- Use multiple API keys with round-robin

### Caching

To avoid re-processing:
- RSSFeedMonitorAgent tracks processed episodes
- Check file storage before re-generating summaries
- Use Redis for distributed caching

---

## Examples

See the `examples/` directory for complete working examples:

- `podcast_intelligence_example.py`: Full podcast workflow
- `document_intelligence_example.py`: Document processing workflow

Run examples:

```bash
python examples/podcast_intelligence_example.py
python examples/document_intelligence_example.py
```

---

## Next Steps

1. **Configure Your Transcript CLI**: Update `TRANSCRIPT_CLI_COMMAND` with your tool
2. **Add RSS Feeds**: Create feed configuration JSON
3. **Set API Keys**: Configure OpenAI or Anthropic
4. **Test Individual Agents**: Run examples to verify setup
5. **Deploy with Orchestrator**: Scale with Kubernetes
6. **Schedule Automated Runs**: Set up daily/weekly automation

---

## Support

For issues or questions:
- Check logs in `/var/log/orchestrator/` or container logs
- Review agent health: `GET /health` endpoint
- Check Redis state: Use Redis CLI to inspect task states
- Enable DEBUG logging: `LOG_LEVEL=DEBUG`

---

## Migration from Placeholder Agents

The original placeholder agents are still available but should be replaced:

**Old Agents** (examples/stubs):
- DataIngestAgent
- DataAnalysisAgent
- SynthesisAgent
- VideoDetectionAgent
- AlertingAgent
- APICallerAgent

**New Agents** (production-ready):
- RSSFeedMonitorAgent
- PodcastTranscriptAgent
- TranscriptSummaryAgent
- DocumentReaderAgent
- IndustrySynthesisAgent

To migrate:
1. Update task type mappings in orchestrator
2. Update agent deployment manifests
3. Test new workflows
4. Decommission old agents
