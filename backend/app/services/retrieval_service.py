import re
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.kb import KBChunk, KBDocument
from app.ai.provider_adapter import ProviderAdapter
from app.constants import RETRIEVAL_MAX_CHARS


async def retrieve_context(
    query: str,
    category: str,
    db: AsyncSession,
    provider: ProviderAdapter,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    clean_words = [
        w.lower()
        for w in re.findall(r"\b\w{3,}\b", query)
        if w.lower() not in {"the", "and", "for", "with", "this", "that", "can", "get", "please"}
    ]

    stmt = (
        select(KBChunk)
        .join(KBDocument, KBChunk.doc_id == KBDocument.doc_id)
        .where(KBDocument.is_adversarial.is_(False))
    )

    if category:
        clean_cat = category.strip().lower()
        stmt = stmt.where(
            or_(
                KBDocument.category == clean_cat,
                KBDocument.category == "general",
                KBDocument.category.is_(None),
            )
        )

    result = await db.execute(stmt)
    matching_chunks = result.scalars().all()

    if not matching_chunks:
        stmt_all = (
            select(KBChunk)
            .join(KBDocument, KBChunk.doc_id == KBDocument.doc_id)
            .where(KBDocument.is_adversarial.is_(False))
            .limit(100)
        )
        res_all = await db.execute(stmt_all)
        matching_chunks = res_all.scalars().all()

    scored_chunks = []
    for chunk in matching_chunks:
        content_lower = (chunk.content or "").lower()
        score = 0.0

        doc_id_lower = (chunk.doc_id or "").lower()
        if category and category.lower() in doc_id_lower:
            score += 5.0

        doc_category = (chunk.metadata_json or {}).get("category", "")
        if category and category.lower() in doc_category.lower():
            score += 3.0

        for word in clean_words:
            if word in content_lower:
                score += 2.0

        if query.lower()[:30] in content_lower:
            score += 4.0

        scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    results = []
    total_length = 0

    for score, chunk in scored_chunks[:top_k]:
        meta = chunk.metadata_json or {}
        chunk_content = chunk.content or ""
        if total_length + len(chunk_content) > RETRIEVAL_MAX_CHARS:
            break

        results.append({
            "chunk_id": chunk.id,
            "doc_id": chunk.doc_id,
            "content": chunk_content,
            "relevance_score": float(score if score > 0 else 0.5),
            "metadata": meta,
        })
        total_length += len(chunk_content)

    return results
