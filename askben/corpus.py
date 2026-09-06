"""Load the corpus: one Markdown file per published answer, with frontmatter.

Everything in corpus/ is public by definition (PLAN.md §0). A file with
`public: false` is skipped at ingest so a draft can sit here without being embedded.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path
import frontmatter

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"

@dataclass(frozen=True)
class Doc:
    slug: str
    title: str      # the question, or a short title
    topic: str
    body: str
    updated: str
    content_hash: str

    @property
    def embed_text(self) -> str:
        # Question + answer embeds better than the answer alone for Q&A retrieval.
        return f"{self.title}\n\n{self.body}"

def load_corpus(corpus_dir: Path = CORPUS_DIR) -> list[Doc]:
    docs: list[Doc] = []
    for path in sorted(corpus_dir.glob("*.md")):
        if path.name.startswith("_") or path.name.upper() == "README.MD":
            continue
        post = frontmatter.load(path)
        if not post.get("public", True):
            continue
        body = post.content.strip()
        if not body:
            continue
        title = str(post.get("question") or post.get("title") or path.stem)
        h = hashlib.sha256((title + "\n" + body).encode()).hexdigest()[:16]
        docs.append(Doc(
            slug=path.stem,
            title=title,
            topic=str(post.get("topic", "")),
            body=body,
            updated=str(post.get("updated", "")),
            content_hash=h,
        ))
    return docs
