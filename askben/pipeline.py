"""The ask pipeline, independent of HTTP so the eval harness can call it in-process."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from . import config, db, llm
from .guard import Policy, load_policy
from .retrieval import Hit, retrieve

@dataclass
class Result:
    answer: str
    outcome: str                     # answered | declined-off-limits | declined-no-source | offline
    citations: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    rule: str | None = None

_policy: Policy | None = None
def policy() -> Policy:
    global _policy
    if _policy is None:
        _policy = load_policy()
    return _policy

def citation(h: Hit) -> dict:
    return {"slug": h.slug, "title": h.title, "url": f"{config.CITATION_BASE}/{h.slug}.md"}

def ask(conn, question: str, history: list[dict] | None = None, *, enabled: bool | None = None) -> Result:
    t0 = time.perf_counter()
    p = policy()
    if not (config.ENABLED if enabled is None else enabled):
        return Result(answer=p.offline_sentence, outcome="offline")
    if db.spend_today_usd(conn) >= config.DAILY_SPEND_CAP_USD:
        return Result(answer=p.offline_sentence, outcome="offline", rule="spend-cap")

    rule = p.match(question)
    if rule:
        return Result(answer=p.decline_sentence, outcome="declined-off-limits", rule=rule,
                      latency_ms=int((time.perf_counter() - t0) * 1000))

    hits = retrieve(conn, question)
    retrieved = [{"slug": h.slug, "score": round(h.score, 4)} for h in hits]
    if not hits or hits[0].score < config.SIMILARITY_THRESHOLD:
        return Result(answer=p.no_source_sentence, outcome="declined-no-source", retrieved=retrieved,
                      latency_ms=int((time.perf_counter() - t0) * 1000))

    g = llm.answer(question, hits, history)
    cost = config.cost_usd(g.input_tokens, g.output_tokens)
    ms = int((time.perf_counter() - t0) * 1000)
    if g.no_source:
        return Result(answer=p.no_source_sentence, outcome="declined-no-source", retrieved=retrieved,
                      input_tokens=g.input_tokens, output_tokens=g.output_tokens, cost_usd=cost, latency_ms=ms)
    by_slug = {h.slug: h for h in hits}
    return Result(
        answer=llm.strip_citations(g.text),
        outcome="answered",
        citations=[citation(by_slug[s]) for s in g.cited],
        retrieved=retrieved, cited=g.cited,
        input_tokens=g.input_tokens, output_tokens=g.output_tokens, cost_usd=cost, latency_ms=ms,
    )
