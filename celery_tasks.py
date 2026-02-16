"""
Celery Tasks for Async Match Processing
"""
import logging
from celery import Celery
from typing import Dict, List
import os
import time
import asyncio
from collections import Counter

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

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def with_timeout(coro, seconds: int = 5):
    return await asyncio.wait_for(coro, timeout=seconds)


@celery_app.task(
    name="process_match_task",
    bind=True,max_retries=3
)
def process_match_task(self, user_data: Dict) -> Dict:
    global success_counter, failure_counter, fallback_counter

    start_time = time.time()
    task_id = self.request.id

    logger.info(f"[{task_id}] Task started for user {user_data['user_id']}")

    try:
        
        self.update_state(state="PROCESSING", meta={"step": "sanitization"})
        logger.info(f"[{task_id}] Phase 1: Sanitization")

        sanitized_bio, enriched_tags, pii_removed = run_async(
            with_timeout(
                ai_service.sanitize_and_enrich_profile(
                    user_data["bio"],
                    user_data["interest_tags"],
                ),
                seconds=5,
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
            with_timeout(
                ai_service.generate_embedding(embedding_text),
                seconds=5,
            )
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
        global failure_counter
        failure_counter += 1

        error_message = str(e)
        logger.error(f"[{task_id}] Error occurred: {error_message}")
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
                logger.warning(f"[{task_id}] Retrying in {retry_delay} seconds")

                raise self.retry(exc=e, countdown=retry_delay)

       
        logger.warning(f"[{task_id}] Switching to fallback mode")

        popular = run_async(db_manager.get_popular_communities(limit=5))

        fallback_result = MatchResult(
            task_id=task_id,
            user_id=user_data["user_id"],
            tier=MatchTier.FALLBACK,
            matches=[_to_community_match(c, 0.0) for c in popular],
            requires_profile_update=True,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )

        return fallback_result.dict()




async def _hybrid_matching_algorithm(
    user_vector: List[float],
    city: str,
    timezone: str,
) -> List[Dict]:

    filtered_communities = await db_manager.filter_communities_by_location(
        city=city,
        timezone=timezone,
        limit=1000,
    )

    if not filtered_communities:
        return await db_manager.get_popular_communities(limit=5)

    community_ids = [c["community_id"] for c in filtered_communities]

    vector_matches = db_manager.vector_search(
        query_vector=user_vector,
        community_ids=community_ids,
        top_k=20,
    )

    community_map = {
        c["community_id"]: c for c in filtered_communities
    }

    enriched_matches = []

    for vm in vector_matches:
        comm_id = vm["community_id"]
        if comm_id in community_map:
            community = community_map[comm_id]
            enriched_matches.append(
                {
                    "community_id": comm_id,
                    "community_name": community["community_name"],
                    "category": community["category"],
                    "match_score": vm["match_score"],
                    "member_count": community["member_count"],
                    "recent_activity": community["recent_activity"],
                }
            )

    return _apply_diversity_filter(enriched_matches)


def _apply_diversity_filter(matches: List[Dict]) -> List[Dict]:
    if len(matches) < 4:
        return matches

    top_3_categories = [m["category"] for m in matches[:3]]

    if len(set(top_3_categories)) == 1:
        dominant_category = top_3_categories[0]

        for i in range(3, len(matches)):
            if matches[i]["category"] != dominant_category:
                diverse_match = matches.pop(i)
                matches.insert(2, diverse_match)
                break

    return matches


async def _apply_decision_engine(
    task_id: str,
    user_id: str,
    user_bio: str,
    matches: List[Dict],
) -> MatchResult:

    if not matches:
        popular = await db_manager.get_popular_communities(limit=5)
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.FALLBACK,
            matches=[_to_community_match(c, 0.0) for c in popular],
            requires_profile_update=True,
            processing_time_ms=0,
        )

    top_match = matches[0]
    top_score = top_match["match_score"]

    if top_score > 0.87:
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.SOULMATE,
            matches=[_to_community_match(top_match)],
            auto_joined_community=top_match["community_id"],
            ai_intro_generated=False,
            processing_time_ms=0,
        )

    elif top_score >= 0.55:
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.EXPLORER,
            matches=[_to_community_match(m) for m in matches[:5]],
            processing_time_ms=0,
        )

    else:
        popular = await db_manager.get_popular_communities(limit=5)
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.FALLBACK,
            matches=[_to_community_match(c, 0.0) for c in popular],
            requires_profile_update=True,
            processing_time_ms=0,
        )


def _to_community_match(
    community: Dict, score: float = None
) -> CommunityMatch:
    return CommunityMatch(
        community_id=community["community_id"],
        community_name=community["community_name"],
        category=community["category"],
        match_score=score
        if score is not None
        else community.get("match_score", 0.0),
        member_count=community["member_count"],
        recent_activity=community.get("recent_activity", 0),
    )
