# ask-ben — working notes for Claude

Retrieval bot behind ask.benkoester.com: FastAPI (`askben/`), Postgres + pgvector, Titan v2 embeddings and Haiku 4.5 on Bedrock via the instance role, a deterministic off-limits guard, a $1/day cap, and `evals/` (ten golden queries, run on change). The README's "Run locally" is authoritative.

## Rules
- Content rule (Ben, 2026-09-05): nothing on the site or in the bot may carry job-search signal; the bot speaks about Ben in the third person and declines employer, colleague, family, health and compensation questions. Corpus files reach `corpus/` only after Ben approves.
- Run `pytest` and `python -m evals.run_eval --dry` before committing; the full eval spends Bedrock money.

## Test and deploy on the host
- Deploy after pushing: `/Users/bkoester/VSCodeProjects_personal/ec2/ec2-apps/scripts/deploy.sh ask-ben ask-ben-api` (port 8084, `/health`). The database is `ask-ben-db`; `ask-ben-eval` is a batch service.
- Logs: `/Users/bkoester/VSCodeProjects_personal/ec2/ec2-apps/scripts/host.sh 'cd /data/apps/config && docker compose logs --tail 50 ask-ben-api'`.
- Data and secrets: `/data/apps/ask-ben-data/`, SSM `/docker-host/ask-*`. Cloudflare Turnstile is enforced.
