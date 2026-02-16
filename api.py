"""
FastAPI Endpoints for Community Matching System
"""
import os
from dotenv import load_dotenv
# Load the `.env` file located next to this module so env vars are available
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from .models import (
    UserProfileInput, 
    TaskStatusResponse, 
    MatchResult,
    MatchTier
)
from .celery_tasks import process_match_task
from .database import db_manager
from .cache import cache_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    # Startup
    await db_manager.initialize_postgres()
    db_manager.initialize_pinecone()
    yield
    # Shutdown
    await db_manager.close()


app = FastAPI(
    title="AI-Powered Community Matching System v2.0",
    description="Intelligent onboarding with <2s matching using hybrid algorithms",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/match", response_model=TaskStatusResponse, status_code=202)
async def initiate_match(profile: UserProfileInput):
    """
    Phase 1: Ingestion - Return Task ID immediately (<50ms)
    
    Client-side validation already performed.
    Returns Task ID for async processing.
    """
    # Dispatch to Celery (async)
    task = process_match_task.apply_async(
        kwargs={"user_data": profile.dict()},
        task_id=None,  # Auto-generate
        expires=10  # Task expires after 10 seconds
    )
    
    return TaskStatusResponse(
        task_id=task.id,
        status="processing",
        estimated_time_ms=2000,
        websocket_channel=f"match_updates_{profile.user_id}"
    )


@app.get("/api/v1/match/{task_id}")
async def get_match_result(task_id: str):
    """
    Poll for match result
    
    Alternative to WebSocket for clients that prefer HTTP polling
    """
    task = process_match_task.AsyncResult(task_id)

    # Task not yet picked up
    if task.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "processing"
        }

    # Task currently executing
    elif task.state == "STARTED":
        return {
            "task_id": task_id,
            "status": "processing"
        }

    # Task completed successfully
    elif task.state == "SUCCESS":
        return MatchResult(**task.result)

    # Task failed (e.g., OpenAI quota error)
    elif task.state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(task.info)
        }

    # Any other Celery state (RETRY, etc.)
    else:
        return {
            "task_id": task_id,
            "status": task.state.lower()
        }



@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "postgres": "connected" if db_manager.pg_pool else "disconnected",
        "pinecone": "connected" if db_manager.pinecone_index else "disconnected",
        "redis": "connected"
    }


@app.get("/api/v1/popular-communities")
async def get_popular_communities(limit: int = 10):
    """Get popular communities (for fallback UI)"""
    communities = await db_manager.get_popular_communities(limit=limit)
    return {"communities": communities}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
