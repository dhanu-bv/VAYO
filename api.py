"""
FastAPI Endpoints for AI-Powered Community Matching System
"""
from database import SessionLocal, Community, MatchTask
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from models import (
    UserProfileInput,
    TaskStatusResponse,
    MatchResult
)

from database import SessionLocal, Community


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_communities_by_location(
    db: Session,
    city: str,
    timezone: str
):
    return (
        db.query(Community)
        .filter(
            Community.city == city,
            Community.timezone == timezone
        )
        .all()
    )

app = FastAPI(
    title="Community Matching API",
    description="AI-powered community matching system",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/match", response_model=TaskStatusResponse, status_code=202)
async def request_community_match(
    profile: UserProfileInput,
    db: Session = Depends(get_db_session)
):
    try:
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        # Phase A: location filter (already working)
        communities = get_communities_by_location(
            db,
            profile.city,
            profile.timezone
        )
        print(f"[INFO] Found {len(communities)} communities for location")

        # 🔹 STORE TASK IN DB
        task = MatchTask(
            task_id=task_id,
            user_id=profile.user_id,
            status="processing"
        )
        db.add(task)
        db.commit()

        return TaskStatusResponse(
            task_id=task_id,
            status="processing",
            estimated_time_ms=2000,
            websocket_channel=f"match_updates_{profile.user_id}"
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate matching: {str(e)}"
        )

@app.get("/api/v1/match/{task_id}", response_model=MatchResult)
async def get_match_status(
    task_id: str,
    db: Session = Depends(get_db_session)
):
    raise HTTPException(
        status_code=404,
        detail=f"Task {task_id} not found or still processing"
    )

@app.get("/api/v1/match/{task_id}", response_model=MatchResult)
async def get_match_status(
    task_id: str,
    db: Session = Depends(get_db_session)
):
    task = db.query(MatchTask).filter(MatchTask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "processing":
        raise HTTPException(
            status_code=202,
            detail="Task still processing"
        )

    return task.result

@app.post("/api/v1/profile/sanitize")
async def sanitize_profile(profile: UserProfileInput):
    raise HTTPException(
        status_code=501,
        detail="Profile sanitization not yet implemented"
    )

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    return {
        "message": "AI Community Matching API",
        "docs": "/docs",
        "health": "/api/v1/health"
    }
