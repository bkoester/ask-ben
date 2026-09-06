"""Embed the corpus into Postgres. Re-embeds only documents whose content changed.

    python -m askben.ingest            # upsert changed docs, delete removed ones
    python -m askben.ingest --force    # re-embed everything
"""
from __future__ import annotations
import json
import sys
from . import db
from .corpus import load_corpus
from .embeddings import embed

def main(force: bool = False) -> None:
    db.init_schema()
    docs = load_corpus()
    with db.connect() as conn:
        existing = {slug: h for slug, h in conn.execute("SELECT slug, content_hash FROM corpus.documents")}
        todo = [d for d in docs if force or existing.get(d.slug) != d.content_hash]
        gone = set(existing) - {d.slug for d in docs}
        if todo:
            vectors = embed([d.embed_text for d in todo], task="retrieval.passage")
            for d, v in zip(todo, vectors):
                conn.execute(
                    """INSERT INTO corpus.documents (slug, title, topic, body, updated, content_hash, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (slug) DO UPDATE SET title=EXCLUDED.title, topic=EXCLUDED.topic,
                         body=EXCLUDED.body, updated=EXCLUDED.updated, content_hash=EXCLUDED.content_hash,
                         embedding=EXCLUDED.embedding, embedded_at=now()""",
                    (d.slug, d.title, d.topic, d.body, d.updated, d.content_hash, v),
                )
        for slug in gone:
            conn.execute("DELETE FROM corpus.documents WHERE slug = %s", (slug,))
        conn.commit()
    print(json.dumps({"total": len(docs), "embedded": len(todo), "removed": sorted(gone)}))

if __name__ == "__main__":
    main(force="--force" in sys.argv)
