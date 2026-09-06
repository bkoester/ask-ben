"""Jina Embeddings v3 (same provider and model as the journal app)."""
from __future__ import annotations
import httpx
from . import config

JINA_URL = "https://api.jina.ai/v1/embeddings"

def embed(texts: list[str], task: str) -> list[list[float]]:
    """task is 'retrieval.passage' for documents and 'retrieval.query' for questions."""
    if not config.JINA_API_KEY:
        raise RuntimeError("JINA_API_KEY is not set")
    r = httpx.post(
        JINA_URL,
        headers={"Authorization": f"Bearer {config.JINA_API_KEY}"},
        json={"model": config.JINA_MODEL, "input": texts, "task": task,
              "dimensions": config.EMBEDDING_DIM},
        timeout=60.0,
    )
    r.raise_for_status()
    data = sorted(r.json()["data"], key=lambda x: x["index"])
    return [d["embedding"] for d in data]
