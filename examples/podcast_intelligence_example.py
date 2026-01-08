"""
Podcast Intelligence Workflow Example

This example demonstrates the complete podcast intelligence pipeline:
1. Monitor RSS feeds for new episodes
2. Create transcripts from audio
3. Generate summaries with insights
4. Synthesize cross-episode intelligence

Usage:
    python examples/podcast_intelligence_example.py
"""

import asyncio
import uuid
from datetime import datetime

from core.orchestrator import Orchestrator, TaskDefinition
from core.execution_engine import ExecutionMode
from agents.rss_feed_monitor_agent import RSSFeedMonitorAgent, AgentInput
from agents.podcast_transcript_agent import PodcastTranscriptAgent
from agents.transcript_summary_agent import TranscriptSummaryAgent
from agents.industry_synthesis_agent import IndustrySynthesisAgent


async def example_1_check_rss_feeds():
    """
    Example 1: Monitor RSS feeds for new podcast episodes
    """
    print("\n" + "="*80)
    print("Example 1: Checking RSS Feeds for New Episodes")
    print("="*80)

    # Create agent
    agent = RSSFeedMonitorAgent("rss-monitor-001")

    # Configure feeds
    feed_config = {
        "feeds": [
            {
                "feed_url": "https://example.com/podcast/feed.xml",
                "feed_name": "Tech Talks Daily",
                "enabled": True,
                "check_frequency_hours": 24,
                "tags": ["technology", "business"]
            },
            {
                "feed_url": "https://example.com/another-podcast/feed.xml",
                "feed_name": "Industry Insights",
                "enabled": True,
                "check_frequency_hours": 24,
                "tags": ["industry", "analysis"]
            }
        ]
    }

    # Create input
    inputs = [
        AgentInput(
            input_id="feed-config-1",
            input_type="feed_config",
            data=feed_config,
            metadata={}
        )
    ]

    # Process
    parameters = {
        "lookback_days": 7,
        "force_refresh": True
    }

    result = await agent.process(inputs, parameters)

    print(f"\nFound {result.data['new_count']} new episodes")
    print(f"Checked {result.data['feeds_checked']} feeds")

    if result.data['episodes']:
        print("\nNew Episodes:")
        for episode in result.data['episodes'][:5]:  # Show first 5
            print(f"  - {episode['title']}")
            print(f"    Podcast: {episode['podcast_name']}")
            print(f"    Published: {episode['publish_date']}")
            print(f"    Audio URL: {episode['audio_url']}")
            print()

    return result.data['episodes']


async def example_2_transcribe_podcast(episode_data):
    """
    Example 2: Create transcript from podcast episode
    """
    print("\n" + "="*80)
    print("Example 2: Creating Transcript from Podcast")
    print("="*80)

    # Create agent
    agent = PodcastTranscriptAgent("transcript-001")

    # Create input from episode data
    inputs = [
        AgentInput(
            input_id=episode_data.get("episode_id", "episode-1"),
            input_type="episode",
            data=episode_data,
            metadata={}
        )
    ]

    # Process
    parameters = {
        "include_timestamps": True,
        "include_speakers": True,
        "output_format": "markdown",
        "save_to_storage": True
    }

    result = await agent.process(inputs, parameters)

    print(f"\nTranscription complete!")
    print(f"Success: {result.data['success_count']}")
    print(f"Failed: {result.data['failed_count']}")

    if result.data['transcripts']:
        transcript_info = result.data['transcripts'][0]
        if 'error' not in transcript_info:
            print(f"\nTranscript Details:")
            print(f"  Word Count: {transcript_info['word_count']}")
            print(f"  File Path: {transcript_info['file_path']}")
            return transcript_info
        else:
            print(f"\nError: {transcript_info['error']}")
            return None


async def example_3_summarize_transcript(transcript_info):
    """
    Example 3: Generate summary from transcript
    """
    print("\n" + "="*80)
    print("Example 3: Generating Summary from Transcript")
    print("="*80)

    # Create agent
    agent = TranscriptSummaryAgent("summary-001")

    # Create input
    inputs = [
        AgentInput(
            input_id="transcript-1",
            input_type="transcript",
            data=transcript_info['transcript'],
            metadata={
                "episode_id": transcript_info['episode_id'],
                "title": transcript_info['title']
            }
        )
    ]

    # Process
    parameters = {
        "summary_length": "medium",
        "include_quotes": True,
        "include_topics": True,
        "include_insights": True,
        "industry_tags": [
            "Technology", "Business", "Healthcare",
            "Finance", "Manufacturing", "Retail"
        ],
        "save_to_storage": True
    }

    result = await agent.process(inputs, parameters)

    print(f"\nSummary generated!")
    print(f"LLM Model: {result.metadata['llm_model']}")

    if result.data['summaries']:
        summary_info = result.data['summaries'][0]
        if 'error' not in summary_info:
            print(f"\nSummary Details:")
            print(f"  File Path: {summary_info['file_path']}")

            # Print executive summary
            summary_data = summary_info['summary']
            if summary_data.get('executive_summary'):
                print(f"\nExecutive Summary:")
                print(f"  {summary_data['executive_summary'][:200]}...")

            # Print key insights
            if summary_data.get('key_insights'):
                print(f"\nKey Insights:")
                for insight in summary_data['key_insights'][:3]:
                    print(f"  - {insight}")

            return summary_info
        else:
            print(f"\nError: {summary_info['error']}")
            return None


async def example_4_synthesize_intelligence(summaries):
    """
    Example 4: Synthesize intelligence from multiple summaries
    """
    print("\n" + "="*80)
    print("Example 4: Synthesizing Industry Intelligence")
    print("="*80)

    # Create agent
    agent = IndustrySynthesisAgent("synthesis-001")

    # Create inputs
    inputs = [
        AgentInput(
            input_id=f"summary-{i}",
            input_type="summary",
            data=summary,
            metadata={}
        )
        for i, summary in enumerate(summaries)
    ]

    # Process
    parameters = {
        "report_type": "weekly",
        "industries": [
            "Technology", "Business", "Healthcare",
            "Finance", "Manufacturing", "Retail"
        ],
        "include_trends": True,
        "include_topics": True,
        "include_comparison": True,
        "min_frequency": 2,
        "save_to_storage": True
    }

    result = await agent.process(inputs, parameters)

    print(f"\nIntelligence synthesis complete!")
    print(f"Summaries analyzed: {result.data['summary_count']}")
    print(f"File Path: {result.data['file_path']}")

    # Print report excerpt
    report = result.data['report']
    if report.get('executive_summary'):
        print(f"\nExecutive Summary:")
        print(f"  {report['executive_summary'][:300]}...")

    # Print key themes
    if report.get('key_themes'):
        print(f"\nKey Themes Identified:")
        print(f"  {report['key_themes'][:200]}...")

    return result


async def example_5_full_pipeline_with_orchestrator():
    """
    Example 5: Run complete pipeline using orchestrator
    """
    print("\n" + "="*80)
    print("Example 5: Full Pipeline with Orchestrator")
    print("="*80)

    # Create orchestrator
    orchestrator = Orchestrator(
        redis_host="localhost",
        redis_port=6379,
        max_workers=100
    )

    await orchestrator.start()

    # Define task
    task_def = TaskDefinition(
        task_id=f"podcast-intel-{uuid.uuid4().hex[:8]}",
        task_type="podcast_intelligence",
        inputs=[
            {
                "input_type": "feed_config",
                "data": {
                    "feeds": [
                        {
                            "feed_url": "https://example.com/podcast/feed.xml",
                            "feed_name": "Tech Talks Daily",
                            "enabled": True
                        }
                    ]
                }
            }
        ],
        execution_mode=ExecutionMode.SEQUENTIAL,
        priority=5,
        timeout_ms=300000,  # 5 minutes
        metadata={
            "user": "analyst-001",
            "report_period": "weekly"
        }
    )

    # Submit task
    print(f"\nSubmitting task: {task_def.task_id}")
    response = await orchestrator.submit_task(task_def)

    print(f"Task submitted: {response['task_id']}")
    print(f"Status: {response['status']}")

    # Monitor task
    print("\nMonitoring task execution...")
    for i in range(60):  # Monitor for up to 60 seconds
        await asyncio.sleep(1)
        status = await orchestrator.get_task_status(task_def.task_id)

        if status['status'] == 'COMPLETED':
            print(f"\nTask completed successfully!")
            print(f"Execution time: {status.get('execution_time_ms', 0)}ms")
            break
        elif status['status'] == 'FAILED':
            print(f"\nTask failed: {status.get('error')}")
            break
        else:
            print(f"  Status: {status['status']}... ({i+1}s)", end='\r')

    await orchestrator.stop()


async def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("PODCAST INTELLIGENCE WORKFLOW EXAMPLES")
    print("="*80)

    # Note: These examples demonstrate the API usage.
    # In production, you would:
    # 1. Configure actual RSS feed URLs
    # 2. Set up your transcript CLI tool
    # 3. Configure LLM API keys
    # 4. Set up Redis server

    print("\nPrerequisites:")
    print("  1. Redis server running on localhost:6379")
    print("  2. Environment variables set:")
    print("     - LLM_PROVIDER (openai or anthropic)")
    print("     - OPENAI_API_KEY or ANTHROPIC_API_KEY")
    print("     - TRANSCRIPT_CLI_COMMAND (path to your transcript CLI)")
    print("  3. RSS feed URLs configured")
    print("\nNote: These are demonstration examples showing the API structure.")
    print("Actual execution requires the above prerequisites.\n")

    # Uncomment to run individual examples:

    # Example 1: Check RSS feeds
    # episodes = await example_1_check_rss_feeds()

    # Example 2: Transcribe a podcast (requires episode data)
    # if episodes:
    #     transcript = await example_2_transcribe_podcast(episodes[0])

    # Example 3: Summarize transcript (requires transcript)
    #     if transcript:
    #         summary = await example_3_summarize_transcript(transcript)

    # Example 4: Synthesize intelligence (requires multiple summaries)
    #         if summary:
    #             await example_4_synthesize_intelligence([summary])

    # Example 5: Full pipeline with orchestrator
    # await example_5_full_pipeline_with_orchestrator()

    print("\nTo run these examples, uncomment the desired example calls above")
    print("and ensure all prerequisites are met.")


if __name__ == "__main__":
    asyncio.run(main())
