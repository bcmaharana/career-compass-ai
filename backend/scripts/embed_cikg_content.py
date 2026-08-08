"""Generate/refresh embeddings for CIKG search (Phase 4.5.1 MVP 2A).

Idempotent — EmbeddingIndexingService.reindex_all() only calls the
embedding provider for content that's new or has changed since its last
embed (compared via source_text_hash), so re-running after this is a
cheap no-op until seed content actually changes.

Requires Ollama running and reachable (OLLAMA_BASE_URL), with
Settings.cikg_embedding_model (default "nomic-embed-text") pulled:

    ollama pull nomic-embed-text

Run after scripts/seed_cikg_mvp1.py:

    python scripts/embed_cikg_content.py
"""

from __future__ import annotations

import asyncio

from app.adapters.ai_providers.ollama_embedding_provider import OllamaEmbeddingProvider
from app.adapters.db.base import async_session_factory
from app.adapters.db.repositories.career_intelligence import (
    SqlAlchemyCikgRoleRepository,
    SqlAlchemyCompetencyRepository,
    SqlAlchemySkillRepository,
)
from app.adapters.db.repositories.search import (
    SqlAlchemyContentEmbeddingRepository,
    SqlAlchemyEmbeddingModelRepository,
)
from app.application.career_intelligence.embedding_service import EmbeddingIndexingService
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def embed_cikg_content() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        service = EmbeddingIndexingService(
            OllamaEmbeddingProvider(settings),
            SqlAlchemyEmbeddingModelRepository(session),
            SqlAlchemyContentEmbeddingRepository(session),
            SqlAlchemySkillRepository(session),
            SqlAlchemyCikgRoleRepository(session),
            SqlAlchemyCompetencyRepository(session),
            model_name=settings.cikg_embedding_model,
            provider_name="ollama",
            dimensions=settings.cikg_embedding_dimensions,
        )
        counts = await service.reindex_all()
        await session.commit()
    logger.info("cikg_embed_complete", **counts)


if __name__ == "__main__":
    asyncio.run(embed_cikg_content())
