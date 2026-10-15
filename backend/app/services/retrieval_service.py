import re
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.kb import KBChunk, KBDocument
from app.ai.provider_adapter import ProviderAdapter
from app.ai.embedding_utils import generate_dense_embedding, cosine_similarity
from app.constants import RETRIEVAL_MAX_CHARS
from app.config import settings

RELEVANCE_CUTOFF = 0.35

def _compute_lexical_score(query: str, content: str) -> float:
    if not query or not content:
        return 0.0
    q_words = [
        w.lower()
        for w in re.findall(r"\b\w{3,}\b", query)
        if w.lower() not in {"the", "and", "for", "with", "this", "that", "can", "get", "please"}
    ]
    if not q_words:
        return 0.0
    c_lower = content.lower()
    matches = sum(1 for w in q_words if w in c_lower)
    return matches / len(q_words)

async def retrieve_context(
    query: str,
    category: str,
    db: AsyncSession,
    provider: ProviderAdapter,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    query_str = (query or "").strip()
    if not query_str:
        return []

    try:
        emb_res = await provider.embed([query_str], settings.EMBEDDING_MODEL)
        query_vector = emb_res.embeddings[0] if emb_res.embeddings else None
    except Exception:
        query_vector = None

    if not query_vector or all(x == 0.0 for x in query_vector):
        query_vector = generate_dense_embedding(query_str)

    clean_cat = category.strip().lower() if category else None

    scored_candidates = []

    try:
        stmt = (
            select(
                KBChunk,
                KBChunk.embedding.cosine_distance(query_vector).label("dist"),
            )
            .join(KBDocument, KBChunk.doc_id == KBDocument.doc_id)
            .where(KBDocument.is_adversarial.is_(False))
            .where(KBChunk.embedding.isnot(None))
        )
        if clean_cat:
            stmt = stmt.where(
                or_(
                    KBDocument.category == clean_cat,
                    KBDocument.category == "general",
                    KBDocument.category.is_(None),
                )
            )

        stmt = stmt.order_by("dist").limit(top_k * 3)
        res = await db.execute(stmt)
        rows = res.all()

        for row in rows:
            chunk = row[0]
            dist = float(row[1]) if row[1] is not None else 1.0
            vec_sim = max(0.0, 1.0 - (dist / 2.0))
            lex_score = _compute_lexical_score(query_str, chunk.content or "")
            hybrid_score = (0.70 * vec_sim) + (0.30 * lex_score)

            if clean_cat:
                doc_cat = (chunk.metadata_json or {}).get("category", "")
                if clean_cat in str(chunk.doc_id or "").lower() or clean_cat in doc_cat.lower():
                    hybrid_score += 0.08

            scored_candidates.append((hybrid_score, chunk))

    except Exception:
        stmt_fallback = (
            select(KBChunk)
            .join(KBDocument, KBChunk.doc_id == KBDocument.doc_id)
            .where(KBDocument.is_adversarial.is_(False))
        )
        if clean_cat:
            stmt_fallback = stmt_fallback.where(
                or_(
                    KBDocument.category == clean_cat,
                    KBDocument.category == "general",
                    KBDocument.category.is_(None),
                )
            )

        res_fallback = await db.execute(stmt_fallback)
        all_chunks = res_fallback.scalars().all()

        for chunk in all_chunks:
            if chunk.embedding is not None and isinstance(chunk.embedding, (list, tuple)):
                vec_sim = max(0.0, cosine_similarity(list(chunk.embedding), query_vector))
            else:
                chunk_vec = generate_dense_embedding(chunk.content or "")
                vec_sim = max(0.0, cosine_similarity(chunk_vec, query_vector))

            lex_score = _compute_lexical_score(query_str, chunk.content or "")
            hybrid_score = (0.70 * vec_sim) + (0.30 * lex_score)

            if clean_cat:
                doc_cat = (chunk.metadata_json or {}).get("category", "")
                if clean_cat in str(chunk.doc_id or "").lower() or clean_cat in doc_cat.lower():
                    hybrid_score += 0.08

            scored_candidates.append((hybrid_score, chunk))

    scored_candidates = [
        (score, chunk) for score, chunk in scored_candidates if score >= RELEVANCE_CUTOFF
    ]
    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    results = []
    total_length = 0

    for score, chunk in scored_candidates[:top_k]:
        meta = chunk.metadata_json or {}
        chunk_content = chunk.content or ""
        if total_length + len(chunk_content) > RETRIEVAL_MAX_CHARS:
            break

        results.append({
            "chunk_id": chunk.id,
            "doc_id": chunk.doc_id,
            "content": chunk_content,
            "relevance_score": round(float(score), 4),
            "metadata": meta,
        })
        total_length += len(chunk_content)

    return results
