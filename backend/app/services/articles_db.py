# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import math
import re
import threading
from collections import Counter
from typing import Any

import chromadb

from app.config import CHROMA_DIR

COLLECTION = "articles"

_TOKEN_RE = re.compile(r"[0-9a-zA-Zа-яА-ЯёЁ]+")
_BM25_K1 = 1.5
_BM25_B = 0.75
_RRF_K = 60

_index_lock = threading.Lock()
_index: dict[str, Any] | None = None


def _tokenize(text: str | None) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


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
    _invalidate_index()
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
                "doc_id": doc_id,
                "article_id": meta.get("article_id"),
                "title": meta.get("title", ""),
                "chunk": doc,
                "distance": round(float(dist), 4),
            }
        )
    return results


def _invalidate_index() -> None:
    global _index
    with _index_lock:
        _index = None


def reset_cache() -> None:
    """Сбрасывает кэш BM25 (например, после восстановления из копии)."""
    _invalidate_index()


def _ensure_index() -> dict[str, Any]:
    """Лениво строит инвертированный индекс фрагментов для BM25.

    Строится под блокировкой, поэтому не конфликтует с invalidation
    из add_chunks/delete_article: если параллельная операция сбросит
    индекс, следующий вызов просто перестроит его заново.
    """
    global _index
    with _index_lock:
        if _index is not None:
            return _index
        coll = _collection()
        index: dict[str, Any] = {
            "postings": {},
            "doc_len": {},
            "meta": {},
            "num_docs": 0,
            "total_len": 0,
            "avg_len": 0.0,
        }
        if coll.count():
            data = coll.get(include=["documents", "metadatas"])
            ids = data.get("ids", [])
            docs = data.get("documents", [])
            metas = data.get("metadatas", [])
            postings = index["postings"]
            for i, doc_id in enumerate(ids):
                meta = metas[i] if i < len(metas) else None
                index["meta"][doc_id] = {
                    "article_id": (meta or {}).get("article_id"),
                    "title": (meta or {}).get("title", ""),
                }
                tf: Counter[str] = Counter(
                    _tokenize(docs[i] if i < len(docs) else None)
                )
                index["doc_len"][doc_id] = sum(tf.values())
                index["total_len"] += sum(tf.values())
                for term, count in tf.items():
                    postings.setdefault(term, {})[doc_id] = count
            index["num_docs"] = len(ids)
            index["avg_len"] = (
                index["total_len"] / index["num_docs"]
                if index["num_docs"]
                else 0.0
            )
        _index = index
        return index


def _bm25_search(
    index: dict[str, Any],
    query_text: str,
    top_k: int,
    article_id: int | None = None,
) -> list[str]:
    """Возвращает doc_id фрагментов, отсортированные по BM25."""
    postings = index["postings"]
    scores: dict[str, float] = {}
    num_docs = index["num_docs"]
    avg_len = index["avg_len"]
    if not num_docs:
        return []
    for term in set(_tokenize(query_text)):
        posting = postings.get(term)
        if not posting:
            continue
        df = len(posting)
        idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
        for doc_id, tf in posting.items():
            if (
                article_id is not None
                and index["meta"][doc_id]["article_id"] != article_id
            ):
                continue
            dl = index["doc_len"].get(doc_id, 0)
            if avg_len > 0:
                norm = (tf * (_BM25_K1 + 1.0)) / (
                    tf
                    + _BM25_K1
                    * (1.0 - _BM25_B + _BM25_B * (dl / avg_len))
                )
            else:
                norm = tf
            scores[doc_id] = scores.get(doc_id, 0.0) + idf * norm
    return [d for d, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:top_k]]


def hybrid_query(
    query_text: str,
    embedding: list[float],
    limit: int = 5,
    article_id: int | None = None,
) -> list[dict[str, Any]]:
    """Гибридный поиск фрагментов: векторный (семантика) + BM25 (термины),
    слияние результатов через Reciprocal Rank Fusion."""
    limit = max(1, min(int(limit), 20))
    coll = _collection()
    count = coll.count()
    if count == 0:
        return []
    pool = min(max(limit * 4, 12), count)
    vec_results = query(embedding, pool, article_id)
    vec_map = {r["doc_id"]: r for r in vec_results}

    fused: dict[str, float] = {}
    for rank, r in enumerate(vec_results):
        fused[r["doc_id"]] = fused.get(r["doc_id"], 0.0) + 1.0 / (_RRF_K + rank + 1)
    if query_text and query_text.strip():
        for rank, doc_id in enumerate(
            _bm25_search(_ensure_index(), query_text, pool, article_id)
        ):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
    if not fused:
        return []

    top_ids = [d for d, _ in sorted(fused.items(), key=lambda kv: -kv[1])[:limit]]
    data = coll.get(ids=top_ids, include=["documents", "metadatas"])
    got = data.get("ids", [])
    pos = {doc_id: i for i, doc_id in enumerate(got)}
    results: list[dict[str, Any]] = []
    for doc_id in top_ids:
        if doc_id not in pos:
            continue
        meta = data["metadatas"][pos[doc_id]] or {}
        results.append(
            {
                "doc_id": doc_id,
                "article_id": meta.get("article_id"),
                "title": meta.get("title", ""),
                "chunk": data["documents"][pos[doc_id]],
                "distance": vec_map.get(doc_id, {}).get("distance"),
                "score": round(fused[doc_id], 4),
            }
        )
    return results


def delete_article(article_id: int) -> None:
    coll = _collection()
    coll.delete(where={"article_id": article_id})
    _invalidate_index()
