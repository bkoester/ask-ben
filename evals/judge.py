"""LLM judge for answerable cases. Deterministic checks run first; the judge only grades quality."""
from __future__ import annotations
import json
from anthropic import AnthropicBedrock
from askben import config

JUDGE_SYSTEM = """You grade an answer produced by a retrieval bot about Ben Koester's writing.
Given the QUESTION, the SOURCES the bot was allowed to use, and the ANSWER, decide:
- faithful: every claim in the answer is supported by the sources (true/false)
- responsive: the answer addresses the question rather than something nearby (true/false)
- third_person: the answer speaks about Ben, never as Ben (true/false)
Reply with JSON only: {"faithful": bool, "responsive": bool, "third_person": bool, "reason": "<one sentence>"}"""

_client: AnthropicBedrock | None = None
def client() -> AnthropicBedrock:
    global _client
    if _client is None:
        _client = AnthropicBedrock(aws_region=config.BEDROCK_REGION)
    return _client

def judge(question: str, sources: str, answer: str) -> tuple[dict, int, int]:
    resp = client().messages.create(
        model=config.BEDROCK_JUDGE_MODEL, max_tokens=200,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": f"QUESTION: {question}\n\nSOURCES:\n{sources}\n\nANSWER: {answer}"}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    try:
        verdict = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except Exception:
        verdict = {"faithful": False, "responsive": False, "third_person": False, "reason": f"unparseable: {text[:80]}"}
    return verdict, resp.usage.input_tokens, resp.usage.output_tokens
