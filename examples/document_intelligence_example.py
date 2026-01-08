"""
Document Intelligence Workflow Example

This example demonstrates the document intelligence pipeline:
1. Read and extract text from various document formats
2. Generate summaries with insights
3. Synthesize cross-document intelligence

Usage:
    python examples/document_intelligence_example.py
"""

import asyncio
import uuid
from datetime import datetime

from core.orchestrator import Orchestrator, TaskDefinition
from core.execution_engine import ExecutionMode
from agents.document_reader_agent import DocumentReaderAgent, AgentInput
from agents.transcript_summary_agent import TranscriptSummaryAgent
from agents.industry_synthesis_agent import IndustrySynthesisAgent


async def example_1_read_text_file():
    """
    Example 1: Read plain text file
    """
    print("\n" + "="*80)
    print("Example 1: Reading Text File")
    print("="*80)

    agent = DocumentReaderAgent("doc-reader-001")

    inputs = [
        AgentInput(
            input_id="doc-1",
            input_type="file_path",
            data="/path/to/document.txt",  # Update with actual path
            metadata={"document_type": "report"}
        )
    ]

    parameters = {
        "extract_metadata": True,
        "clean_text": True,
        "preserve_formatting": True
    }

    result = await agent.process(inputs, parameters)

    print(f"\nDocuments processed: {result.data['success_count']}")

    if result.data['documents'] and result.data['documents'][0].get('text'):
        doc = result.data['documents'][0]
        print(f"\nDocument Details:")
        print(f"  ID: {doc['document_id']}")
        print(f"  Word Count: {doc['metadata']['word_count']}")
        print(f"  Character Count: {doc['metadata']['character_count']}")
        print(f"\nText Preview:")
        print(f"  {doc['text'][:200]}...")

        return doc


async def example_2_read_pdf():
    """
    Example 2: Extract text from PDF
    """
    print("\n" + "="*80)
    print("Example 2: Extracting Text from PDF")
    print("="*80)

    agent = DocumentReaderAgent("doc-reader-002")

    inputs = [
        AgentInput(
            input_id="pdf-1",
            input_type="file_path",
            data="/path/to/document.pdf",  # Update with actual path
            metadata={
                "document_type": "research_paper",
                "source": "arxiv"
            }
        )
    ]

    parameters = {
        "extract_metadata": True,
        "clean_text": True
    }

    result = await agent.process(inputs, parameters)

    if result.data['documents']:
        doc = result.data['documents'][0]
        if 'error' not in doc:
            print(f"\nPDF extracted successfully!")
            print(f"  File: {doc['metadata'].get('filename')}")
            print(f"  Size: {doc['metadata'].get('size_bytes')} bytes")
            print(f"  Pages: {doc['metadata'].get('page_count', 'N/A')}")
            print(f"  Word Count: {doc['metadata']['word_count']}")

            return doc
        else:
            print(f"\nError: {doc['error']}")


async def example_3_ocr_image():
    """
    Example 3: Extract text from image using OCR
    """
    print("\n" + "="*80)
    print("Example 3: OCR from Image/Screenshot")
    print("="*80)

    agent = DocumentReaderAgent("doc-reader-003")

    inputs = [
        AgentInput(
            input_id="image-1",
            input_type="screenshot",
            data="/path/to/screenshot.png",  # Update with actual path
            metadata={
                "source": "presentation",
                "slide_number": 5
            }
        )
    ]

    parameters = {
        "extract_metadata": True,
        "clean_text": True,
        "ocr_language": "eng"
    }

    result = await agent.process(inputs, parameters)

    if result.data['documents']:
        doc = result.data['documents'][0]
        if 'error' not in doc:
            print(f"\nOCR complete!")
            print(f"  Method: {doc['metadata'].get('ocr_method')}")
            print(f"  Word Count: {doc['metadata']['word_count']}")
            print(f"\nExtracted Text:")
            print(f"  {doc['text'][:300]}...")

            return doc
        else:
            print(f"\nError: {doc['error']}")


async def example_4_read_multiple_documents():
    """
    Example 4: Read multiple documents in parallel
    """
    print("\n" + "="*80)
    print("Example 4: Reading Multiple Documents")
    print("="*80)

    agent = DocumentReaderAgent("doc-reader-004")

    # Multiple document inputs
    inputs = [
        AgentInput(
            input_id=f"doc-{i}",
            input_type="file_path",
            data=f"/path/to/document{i}.txt",  # Update with actual paths
            metadata={"batch": "weekly_reports", "week": i}
        )
        for i in range(1, 6)  # 5 documents
    ]

    parameters = {
        "extract_metadata": True,
        "clean_text": True
    }

    result = await agent.process(inputs, parameters)

    print(f"\nProcessed {result.data['success_count']} of {len(inputs)} documents")
    print(f"Failed: {result.data['failed_count']}")

    if result.data['documents']:
        print("\nDocuments:")
        for doc in result.data['documents']:
            if 'error' not in doc:
                print(f"  - {doc['document_id']}: {doc['metadata']['word_count']} words")
            else:
                print(f"  - Error: {doc['error']}")

        return result.data['documents']


async def example_5_summarize_document(document):
    """
    Example 5: Generate summary from document
    """
    print("\n" + "="*80)
    print("Example 5: Summarizing Document")
    print("="*80)

    agent = TranscriptSummaryAgent("summary-001")

    inputs = [
        AgentInput(
            input_id="doc-summary-1",
            input_type="transcript",  # Works with any text
            data=document['text'],
            metadata={
                "document_id": document['document_id'],
                "title": document['metadata'].get('filename', 'Document'),
                "source": document['metadata'].get('source', 'Unknown')
            }
        )
    ]

    parameters = {
        "summary_length": "medium",
        "include_quotes": False,  # Not relevant for most documents
        "include_topics": True,
        "include_insights": True,
        "industry_tags": [
            "Technology", "Business", "Healthcare",
            "Finance", "Manufacturing", "Retail"
        ],
        "save_to_storage": True
    }

    result = await agent.process(inputs, parameters)

    if result.data['summaries']:
        summary = result.data['summaries'][0]
        if 'error' not in summary:
            print(f"\nSummary generated!")
            print(f"  File: {summary['file_path']}")

            summary_data = summary['summary']
            if summary_data.get('executive_summary'):
                print(f"\nExecutive Summary:")
                print(f"  {summary_data['executive_summary'][:250]}...")

            if summary_data.get('key_insights'):
                print(f"\nKey Insights:")
                for insight in summary_data['key_insights'][:5]:
                    print(f"  - {insight}")

            return summary


async def example_6_synthesize_documents(document_summaries):
    """
    Example 6: Synthesize intelligence from multiple document summaries
    """
    print("\n" + "="*80)
    print("Example 6: Synthesizing Document Intelligence")
    print("="*80)

    agent = IndustrySynthesisAgent("synthesis-001")

    inputs = [
        AgentInput(
            input_id=f"summary-{i}",
            input_type="summary",
            data=summary,
            metadata={}
        )
        for i, summary in enumerate(document_summaries)
    ]

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
    print(f"  Documents analyzed: {result.data['summary_count']}")
    print(f"  Report saved to: {result.data['file_path']}")

    report = result.data['report']
    if report.get('executive_summary'):
        print(f"\nExecutive Summary:")
        print(f"  {report['executive_summary'][:300]}...")

    # Print analysis data
    analysis = result.data.get('analysis', {})
    if analysis.get('topics'):
        topics = analysis['topics']
        print(f"\nTopic Analysis:")
        print(f"  Unique topics: {topics['total_unique']}")
        print(f"  Recurring topics: {topics['above_threshold']}")

        if topics.get('top_topics'):
            print(f"\n  Top Topics:")
            for topic, count in list(topics['top_topics'].items())[:5]:
                print(f"    - {topic}: {count} mentions")

    return result


async def example_7_full_pipeline_with_orchestrator():
    """
    Example 7: Complete document intelligence pipeline using orchestrator
    """
    print("\n" + "="*80)
    print("Example 7: Full Pipeline with Orchestrator")
    print("="*80)

    orchestrator = Orchestrator(
        redis_host="localhost",
        redis_port=6379,
        max_workers=100
    )

    await orchestrator.start()

    # Define task for document intelligence
    task_def = TaskDefinition(
        task_id=f"doc-intel-{uuid.uuid4().hex[:8]}",
        task_type="document_intelligence",
        inputs=[
            {
                "input_type": "file_path",
                "data": "/path/to/document1.pdf",
                "metadata": {"category": "research"}
            },
            {
                "input_type": "file_path",
                "data": "/path/to/document2.txt",
                "metadata": {"category": "report"}
            },
            {
                "input_type": "screenshot",
                "data": "/path/to/screenshot.png",
                "metadata": {"category": "presentation"}
            }
        ],
        execution_mode=ExecutionMode.SEQUENTIAL,
        priority=5,
        timeout_ms=600000,  # 10 minutes
        metadata={
            "user": "analyst-002",
            "report_period": "weekly"
        }
    )

    print(f"\nSubmitting document intelligence task: {task_def.task_id}")
    response = await orchestrator.submit_task(task_def)

    print(f"Task submitted: {response['task_id']}")
    print(f"Status: {response['status']}")

    # Monitor task execution
    print("\nMonitoring task execution...")
    for i in range(120):  # Up to 2 minutes
        await asyncio.sleep(1)
        status = await orchestrator.get_task_status(task_def.task_id)

        if status['status'] == 'COMPLETED':
            print(f"\n\nTask completed successfully!")
            print(f"Execution time: {status.get('execution_time_ms', 0)}ms")

            # Display results
            if status.get('output'):
                print("\nTask Output:")
                print(f"  {status['output']}")

            break
        elif status['status'] == 'FAILED':
            print(f"\n\nTask failed: {status.get('error')}")
            break
        else:
            print(f"  Status: {status['status']}... ({i+1}s)", end='\r')

    await orchestrator.stop()


async def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("DOCUMENT INTELLIGENCE WORKFLOW EXAMPLES")
    print("="*80)

    print("\nPrerequisites:")
    print("  1. Redis server running on localhost:6379")
    print("  2. Environment variables set:")
    print("     - LLM_PROVIDER (openai or anthropic)")
    print("     - OPENAI_API_KEY or ANTHROPIC_API_KEY")
    print("     - OCR_ENABLED=true (optional, for image processing)")
    print("     - USE_VISION_API=true (optional, for vision-based OCR)")
    print("  3. Document files ready for processing")
    print("  4. Required packages installed:")
    print("     - pip install PyMuPDF pdfplumber beautifulsoup4")
    print("     - pip install pytesseract (optional, for Tesseract OCR)")
    print("\nNote: Update file paths in examples before running.")
    print()

    # Uncomment to run individual examples:

    # Example 1: Read text file
    # doc = await example_1_read_text_file()

    # Example 2: Extract from PDF
    # pdf_doc = await example_2_read_pdf()

    # Example 3: OCR from image
    # ocr_doc = await example_3_ocr_image()

    # Example 4: Read multiple documents
    # documents = await example_4_read_multiple_documents()

    # Example 5: Summarize a document
    # if doc:
    #     summary = await example_5_summarize_document(doc)

    # Example 6: Synthesize intelligence from multiple summaries
    #     if summary:
    #         await example_6_synthesize_documents([summary])

    # Example 7: Full pipeline with orchestrator
    # await example_7_full_pipeline_with_orchestrator()

    print("\nTo run these examples, uncomment the desired example calls above,")
    print("update file paths, and ensure all prerequisites are met.")


if __name__ == "__main__":
    asyncio.run(main())
