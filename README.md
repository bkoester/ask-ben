# ask-ben

A retrieval bot over Ben Koester's published writing, with the evaluation harness beside it.
Serves `ask.benkoester.com`; the widget lives on the static site (`bkoester/site`).

**Design in one paragraph.** The corpus is Markdown answers Ben wrote for publication
(`corpus/`), embedded with Jina v3 into Postgres + pgvector. A question first hits a
deterministic off-limits check (`askben/policy.yaml`); a match is declined without any model
call. Otherwise the top-k documents are retrieved; if the best similarity is below a threshold
the bot says it has nothing from Ben on that. Only then does Haiku 4.5 (Bedrock, instance
role, no API key) write a third-person answer that must cite source slugs. Every query is
logged to an `analytics` schema; a daily spend cap read from that table takes the bot
offline for the day. `evals/` holds a ten-query golden set, deterministic checks, an LLM
judge, and the run history that the site renders as its evaluation page.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env            # add JINA_API_KEY; AWS creds via your normal profile
docker compose up -d db
python -m askben.ingest         # embeds corpus/
uvicorn askben.api:app --reload --port 8090
pytest                          # offline unit tests
python -m evals.run_eval --dry   # guard-only checks, no model calls
python -m evals.run_eval         # full run; writes evals/history/<date>-<sha>.json
```

## Endpoints

| Route | Purpose |
|---|---|
| `POST /ask` | `{question, session_id?, history?, turnstile_token?}` → `{answer, outcome, citations, session_id}`. 429 when rate-limited, 503 when offline/capped. |
| `GET /health` | document count, today's spend, cap |
| `GET /eval/latest` | most recent eval run |
| `GET /stats` | private (basic auth): outcomes by day, recent questions |

## Controls

`ENABLED=false` takes the bot offline with no model calls. `DAILY_SPEND_CAP_USD` (1.00) does
the same automatically for the rest of the local day. Both are read at request time.

## Deploy

Host wiring (compose entry, tunnel sidecar, SSM deploy key and tunnel token) goes in
`ec2-apps`, following the big-ten-jobs pattern. The eval runs on change via
`scripts/eval-on-change.sh`, not on a timer.
