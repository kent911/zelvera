# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

import chromadb

from app.config import CHROMA_DIR

COLLECTION = "articles"


def _client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _collection() -> chromadb.Collection:
    return _client().get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def add_chunks(
    article_id: int,
    title: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> int:
    if not chunks:
        return 0
    coll = _collection()
    coll.add(
        ids=[f"{article_id}:{i}" for i in range(len(chunks))],
        documents=chunks,
        metadatas=[
            {"article_id": article_id, "title": title, "chunk": i}
            for i in range(len(chunks))
        ],
        embeddings=embeddings,
    )
    return len(chunks)


def query(
    embedding: list[float],
    limit: int = 5,
    article_id: int | None = None,
) -> list[dict[str, Any]]:
    coll = _collection()
    if coll.count() == 0:
        return []
    where = {"article_id": article_id} if article_id is not None else None
    result = coll.query(
        query_embeddings=[embedding],
        n_results=min(limit, coll.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]

    results: list[dict[str, Any]] = []
    for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
        results.append(
            {
                "article_id": meta.get("article_id"),
                "title": meta.get("title", ""),
                "chunk": doc,
                "distance": round(float(dist), 4),
            }
        )
    return results


def delete_article(article_id: int) -> None:
    coll = _collection()
    coll.delete(where={"article_id": article_id})
