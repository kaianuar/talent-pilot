"""Example usage of the gRPC-Web and WebSocket clients.

This module demonstrates how to use the frontend clients to interact
with the backend screening service.
"""

import asyncio
import logging
from typing import Optional

from frontend.grpc_client import (
    GRPCWebClient,
    SyncGRPCWebClient,
    ProgressUpdate,
    Question,
    Assessment,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def async_example():
    """Example using the async client."""
    
    print("=" * 60)
    print("ASYNC CLIENT EXAMPLE")
    print("=" * 60)
    print()
    
    # Create client
    client = GRPCWebClient(
        base_url="http://localhost:9000",
        ws_base_url="ws://localhost:9000",
    )
    
    try:
        # Step 1: Start screening
        print("Step 1: Starting screening...")
        result = await client.start_screening(
            candidate_id="candidate-123",
            job_id="job-456",
            match_tier="STRONG_MATCH",
            question_count=3,
        )
        
        if not result.get("success"):
            print(f"Failed to start screening: {result.get('error_message')}")
            return
        
        screening_id = result["screening_id"]
        first_question = result.get("first_question")
        
        print(f"✅ Screening started: {screening_id}")
        if first_question:
            print(f"   First question: {first_question.get('text', 'N/A')}")
        print()
        
        # Step 2: Connect to WebSocket for real-time updates
        print("Step 2: Connecting to WebSocket for real-time updates...")
        
        def on_progress(update: ProgressUpdate):
            print(f"📊 Progress: {update.progress_percentage:.1f}% - {update.status}")
            if update.current_question:
                print(f"   Current question: {update.current_question.text[:50]}...")
        
        def on_error(msg: str):
            print(f"❌ WebSocket error: {msg}")
        
        client.on_progress(on_progress)
        client.on_error(on_error)
        
        await client.connect_websocket(screening_id, "candidate-123")
        print("✅ WebSocket connected")
        print()
        
        # Step 3: Submit answers (in a real app, you'd get these from user input)
        print("Step 3: Submitting answers...")
        
        answers = [
            "I have 5 years of experience with Python and have built several web applications using FastAPI and Django. I'm particularly proud of a microservices architecture I designed that handled 10k requests per second.",
            "When facing a difficult bug, I first try to reproduce it consistently. Then I use logging and debugging tools to isolate the issue. I also don't hesitate to pair program with colleagues to get fresh perspectives.",
            "I'm passionate about clean code and automated testing. I believe in writing tests first (TDD) and maintaining high code coverage. I also enjoy mentoring junior developers.",
        ]
        
        for i, answer in enumerate(answers, 1):
            print(f"  Submitting answer {i}...")
            result = await client.submit_answer(
                screening_id=screening_id,
                candidate_id="candidate-123",
                question_id=f"q{i}",
                answer_text=answer,
                response_time_seconds=30.0,
            )
            
            if result.get("is_complete"):
                print("  ✅ Screening complete!")
                break
            elif result.get("next_question"):
                q = result["next_question"]
                print(f"  Next question: {q.get('text', 'N/A')[:50]}...")
        
        print()
        
        # Step 4: Start WebSocket listener in background
        print("Step 4: Starting WebSocket listener...")
        listen_task = asyncio.create_task(client.listen())
        
        # Let it run for a few seconds to receive any final updates
        await asyncio.sleep(5)
        
        # Cancel listener
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        print("✅ Done!")
        
    finally:
        # Clean up
        await client.close()
        print()
        print("Client closed.")


def sync_example():
    """Example using the synchronous client (for Streamlit)."""
    
    print("=" * 60)
    print("SYNC CLIENT EXAMPLE (for Streamlit)")
    print("=" * 60)
    print()
    
    # Create async client
    async_client = GRPCWebClient()
    
    # Get sync wrapper
    client = async_client.get_sync_client()
    
    try:
        # Step 1: Start screening
        print("Step 1: Starting screening...")
        result = client.start_screening(
            candidate_id="candidate-123",
            job_id="job-456",
            match_tier="STRONG_MATCH",
            question_count=3,
        )
        
        if not result.get("success"):
            print(f"Failed: {result.get('error_message')}")
            return
        
        screening_id = result["screening_id"]
        print(f"✅ Screening started: {screening_id}")
        print()
        
        # Step 2: Submit an answer
        print("Step 2: Submitting answer...")
        result = client.submit_answer(
            screening_id=screening_id,
            candidate_id="candidate-123",
            question_id="q1",
            answer_text="I have 5 years of Python experience...",
            response_time_seconds=30.0,
        )
        
        print(f"✅ Answer submitted")
        if result.get("next_question"):
            print("Next question available")
        if result.get("is_complete"):
            print("Screening complete!")
        print()
        
        print("✅ Sync example completed!")
        
    finally:
        client.close()
        print()
        print("Client closed.")


async def main():
    """Main entry point."""
    
    # Run async example
    await async_example()
    
    print("\n" + "=" * 60 + "\n")
    
    # Run sync example
    sync_example()


if __name__ == "__main__":
    # Run main
    asyncio.run(main())
