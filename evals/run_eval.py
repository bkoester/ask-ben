"""Run the golden set in-process and write evals/history/<date>-<sha>.json.

    python -m evals.run_eval            # full run (needs DB and Bedrock)
    python -m evals.run_eval --dry      # deterministic checks only, no model calls

Triggered on change by scripts/eval-on-change.sh, not on a timer (PLAN.md §4).
"""
from __future__ import annotations
import json
import statistics
from contextlib import nullcontext
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml
from askben import config, db, pipeline
from askben.llm import format_sources
from askben.retrieval import retrieve

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "history"

def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT.parent).decode().strip()
    except Exception:
        return "nogit"

def run(dry: bool = False) -> dict:
    cases = yaml.safe_load((ROOT / "golden.yaml").read_text())["cases"]
    results, cost, latencies = [], 0.0, []
    failure_taxonomy: dict[str, int] = {}

    def fail(kind: str):
        failure_taxonomy[kind] = failure_taxonomy.get(kind, 0) + 1

    with (nullcontext(None) if dry else db.connect()) as conn:
        for c in cases:
            rec = {"id": c["id"], "category": c["category"], "question": c["question"], "checks": {}, "pass": False}
            if dry:
                rule = pipeline.policy().match(c["question"])
                rec["checks"]["guard"] = rule
                rec["pass"] = (c["category"] in ("off-limits", "injection")) == bool(rule)
                if not rec["pass"]:
                    fail("guard-mismatch")
                results.append(rec)
                continue

            r = pipeline.ask(conn, c["question"])
            cost += r.cost_usd
            latencies.append(r.latency_ms)
            rec.update({"outcome": r.outcome, "answer": r.answer, "cited": r.cited,
                        "retrieved": r.retrieved, "cost_usd": round(r.cost_usd, 6), "latency_ms": r.latency_ms})

            if c["category"] == "answerable":
                ok_out = r.outcome == "answered"
                ok_cite = any(s in r.cited for s in c.get("expect_slugs", []))
                low = r.answer.lower()
                ok_must = all(m.lower() in low for m in c.get("must", []))
                ok_not = not any(m.lower() in low for m in c.get("must_not", []))
                rec["checks"].update({"answered": ok_out, "cited_expected": ok_cite, "must": ok_must, "must_not": ok_not})
                if not ok_out: fail("wrong-refusal")
                if ok_out and not ok_cite: fail("wrong-citation")
                if not ok_must or not ok_not: fail("content-check")
                quality = True
                if ok_out:
                    hits = retrieve(conn, c["question"])
                    from evals.judge import judge
                    verdict, ji, jo = judge(c["question"], format_sources(hits), r.answer)
                    cost += config.cost_usd(ji, jo)
                    rec["judge"] = verdict
                    quality = bool(verdict.get("faithful")) and bool(verdict.get("responsive")) and bool(verdict.get("third_person"))
                    if not verdict.get("faithful"): fail("unfaithful")
                    if not verdict.get("third_person"): fail("first-person")
                    if not verdict.get("responsive"): fail("unresponsive")
                rec["pass"] = ok_out and ok_cite and ok_must and ok_not and quality
            else:
                expected = c["expect_outcome"]
                rec["checks"]["outcome"] = r.outcome == expected
                rec["pass"] = r.outcome == expected
                if not rec["pass"]:
                    fail("missed-refusal" if r.outcome == "answered" else "wrong-refusal-type")
            results.append(rec)

    by_cat: dict[str, dict] = {}
    for rec in results:
        d = by_cat.setdefault(rec["category"], {"pass": 0, "total": 0})
        d["total"] += 1
        d["pass"] += int(rec["pass"])
    refusal_cases = [r for r in results if r["category"] != "answerable"]
    n_model = len(latencies) or 1
    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha": git_sha(), "model": config.BEDROCK_MODEL, "judge_model": config.BEDROCK_JUDGE_MODEL,
        "dry": dry, "n": len(results),
        "pass_rate": round(sum(r["pass"] for r in results) / max(len(results), 1), 3),
        "by_category": by_cat,
        "refusal_accuracy": round(sum(r["pass"] for r in refusal_cases) / max(len(refusal_cases), 1), 3),
        "cost_usd_total": round(cost, 5), "cost_per_query_usd": round(cost / n_model, 5),
        "p50_latency_ms": int(statistics.median(latencies)) if latencies else None,
        "failure_taxonomy": failure_taxonomy,
        "cases": results,
    }

def main():
    dry = "--dry" in sys.argv
    out = run(dry=dry)
    HISTORY.mkdir(exist_ok=True)
    name = f"{datetime.now(timezone.utc):%Y-%m-%d}-{out['sha']}{'-dry' if dry else ''}.json"
    (HISTORY / name).write_text(json.dumps(out, indent=2))
    print(f"{name}: pass {out['pass_rate']:.0%} · refusal acc {out['refusal_accuracy']:.0%} · "
          f"${out['cost_usd_total']:.4f} · {out['failure_taxonomy']}")

if __name__ == "__main__":
    main()
