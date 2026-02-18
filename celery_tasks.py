"""
Celery Tasks for Async Match Processing
"""
import logging
from celery import Celery
from typing import Dict, List
import os
import time
import asyncio

from .models import MatchTier, CommunityMatch, MatchResult, SanitizedProfile
from .database import db_manager
from .ai_services import ai_service
from .cache import cache_manager

logger = logging.getLogger(__name__)

success_counter = 0
failure_counter = 0
fallback_counter = 0


celery_app = Celery(
    "matching_system",
    broker=os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_BACKEND_URL", "redis://localhost:6379/1")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=10,
    task_soft_time_limit=8
)

from celery.signals import worker_process_init

@worker_process_init.connect
def init_worker(**kwargs):
    logger.info("Initializing DB for Celery worker...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(db_manager.initialize_postgres())
    db_manager.initialize_pinecone()

    loop.close()

_task_loop = None

def set_task_loop(loop):
    global _task_loop
    _task_loop = loop

def run_async(coro):
    global _task_loop
    if _task_loop is None:
        raise RuntimeError("Task loop not initialized")
    return _task_loop.run_until_complete(coro)

@celery_app.task(
    name="process_match_task",
    bind=True,
    max_retries=3
)
def process_match_task(self, user_data: Dict) -> Dict:
    global success_counter, failure_counter, fallback_counter

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    set_task_loop(loop)

    start_time = time.time()
    task_id = self.request.id

    logger.info(f"[{task_id}] Task started for user {user_data['user_id']}")

    try:
       
        self.update_state(state="PROCESSING", meta={"step": "sanitization"})
        logger.info(f"[{task_id}] Phase 1: Sanitization")

        sanitized_bio, enriched_tags, pii_removed = run_async(
            ai_service.sanitize_and_enrich_profile(
                user_data["bio"],
                user_data["interest_tags"],
            )
        )

        sanitized_profile = SanitizedProfile(
            user_id=user_data["user_id"],
            sanitized_bio=sanitized_bio,
            enriched_tags=enriched_tags,
            city=user_data["city"],
            timezone=user_data["timezone"],
            pii_removed=pii_removed,
        )

       
        self.update_state(state="PROCESSING", meta={"step": "vectorization"})
        logger.info(f"[{task_id}] Phase 2: Vectorization")

        embedding_text = ai_service.create_embedding_payload(
            sanitized_bio,
            enriched_tags,
        )

        user_vector = run_async(
            ai_service.generate_embedding(embedding_text)
        )

        cache_manager.set_user_vector(
            user_data["user_id"], user_vector, ttl=604800
        )

        
        self.update_state(state="PROCESSING", meta={"step": "hybrid_matching"})
        logger.info(f"[{task_id}] Phase 3: Hybrid Matching")

        matches = run_async(
            _hybrid_matching_algorithm(
                user_vector=user_vector,
                city=sanitized_profile.city,
                timezone=sanitized_profile.timezone,
            )
        )

        
        self.update_state(state="PROCESSING", meta={"step": "decision_engine"})
        logger.info(f"[{task_id}] Phase 4: Decision Engine")

        result = run_async(
            _apply_decision_engine(
                task_id=task_id,
                user_id=user_data["user_id"],
                user_bio=sanitized_bio,
                matches=matches,
            )
        )

        processing_time = int((time.time() - start_time) * 1000)
        result.processing_time_ms = processing_time

        cache_manager.publish_match_result(
            user_data["user_id"], result.dict()
        )

        success_counter += 1
        logger.info(
            f"[{task_id}] Completed successfully in {processing_time} ms | Success count: {success_counter}"
        )

        return result.dict()

    except Exception as e:
        failure_counter += 1
        error_message = str(e)

        logger.error(f"[{task_id}] Error: {error_message}")
        logger.error(f"[{task_id}] Retry count: {self.request.retries}")

        transient_errors = [
            "429",
            "timeout",
            "ConnectionError",
            "ServiceUnavailable",
            "Temporary"
        ]

        if any(err in error_message for err in transient_errors):
            if self.request.retries < self.max_retries:
                retry_delay = 2 ** self.request.retries
                logger.warning(f"[{task_id}] Retrying in {retry_delay}s")
                raise self.retry(exc=e, countdown=retry_delay)

        logger.warning(f"[{task_id}] Switching to fallback mode")

        popular = run_async(db_manager.get_popular_communities(limit=5))

        fallback_counter += 1

        fallback_result = MatchResult(
            task_id=task_id,
            user_id=user_data["user_id"],
            tier=MatchTier.FALLBACK,
            matches=[_to_community_match(c, 0.0) for c in popular],
            requires_profile_update=True,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )

        return fallback_result.dict()

    finally:
        if not loop.is_closed():
            loop.close()
