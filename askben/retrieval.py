from __future__ import annotations
from dataclasses import dataclass
from . import config
from .embeddings import embed

@dataclass(frozen=True)
class Hit:
    slug: str
    title: str
    body: str
    score: float  # cosine similarity in [−1, 1]

def retrieve(conn, question: str, top_k: int = config.TOP_K) -> list[Hit]:
    qv = embed([question], task="retrieval.query")[0]
    rows = conn.execute(
        """SELECT slug, title, body, 1 - (embedding <=> %s::vector) AS score
           FROM corpus.documents ORDER BY embedding <=> %s::vector LIMIT %s""",
        (qv, qv, top_k),
    ).fetchall()
    return [Hit(slug=r[0], title=r[1], body=r[2], score=float(r[3])) for r in rows]
