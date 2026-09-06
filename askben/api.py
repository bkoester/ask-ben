"""FastAPI surface: POST /ask, GET /health, GET /eval/latest, GET /stats (basic auth)."""
from __future__ import annotations
import hashlib
import json
import secrets
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from . import config, db, pipeline

app = FastAPI(title="ask-ben", docs_url=None, redoc_url=None)

@app.on_event("startup")
def _startup():
    # Creates the vector extension, schemas and tables if missing. Ingest still owns embeddings.
    db.init_schema_with_retry()
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS or ["*"],
                   allow_origin_regex=config.ALLOWED_ORIGIN_REGEX,
                   allow_methods=["POST", "GET"], allow_headers=["content-type"])

HISTORY_DIR = Path(__file__).resolve().parent.parent / "evals" / "history"

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_CHARS)
    session_id: str | None = None
    history: list[dict] = Field(default_factory=list)
    turnstile_token: str | None = None

# --- helpers -----------------------------------------------------------------

def ip_hash(request: Request) -> str:
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
    return hashlib.sha256(f"{config.IP_HASH_SALT}:{ip}".encode()).hexdigest()[:24]

_buckets: dict[str, deque] = defaultdict(deque)
def rate_limited(key: str) -> bool:
    now = time.time()
    q = _buckets[key]
    while q and q[0] < now - 600:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_10MIN:
        return True
    q.append(now)
    return False

def turnstile_ok(token: str | None, ip: str | None) -> bool | None:
    """None = check disabled (no secret configured)."""
    if not config.TURNSTILE_SECRET:
        return None
    if not token:
        return False
    try:
        r = httpx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                       data={"secret": config.TURNSTILE_SECRET, "response": token, "remoteip": ip or ""},
                       timeout=10.0)
        return bool(r.json().get("success"))
    except Exception:
        return False

# --- routes ------------------------------------------------------------------

@app.get("/health")
def health():
    try:
        with db.connect() as conn:
            n = conn.execute("SELECT count(*) FROM corpus.documents").fetchone()[0]
            spend = db.spend_today_usd(conn)
        return {"ok": True, "enabled": config.ENABLED, "documents": n,
                "spend_today_usd": round(spend, 4), "cap_usd": config.DAILY_SPEND_CAP_USD}
    except Exception as e:  # DB down: still answer, so the widget can show "asleep" vs "error"
        return JSONResponse({"ok": False, "error": str(e)}, status_code=503)

@app.post("/ask")
def ask(body: AskRequest, request: Request):
    key = ip_hash(request)
    if rate_limited(key):
        with db.connect() as conn:
            db.log_query(conn, ip_hash=key, session_id=body.session_id, question=body.question,
                         outcome="rate-limited")
        raise HTTPException(status_code=429, detail="Too many questions; try again in a few minutes.")
    ts_ok = turnstile_ok(body.turnstile_token, request.headers.get("cf-connecting-ip"))
    if ts_ok is False:
        raise HTTPException(status_code=403, detail="Turnstile check failed.")

    session_id = body.session_id or uuid.uuid4().hex
    with db.connect() as conn:
        r = pipeline.ask(conn, body.question, body.history)
        db.log_query(conn, session_id=session_id, ip_hash=key, question=body.question, answer=r.answer,
                     outcome=r.outcome, retrieved=Jsonb(r.retrieved), cited=Jsonb(r.cited),
                     input_tokens=r.input_tokens, output_tokens=r.output_tokens, cost_usd=r.cost_usd,
                     latency_ms=r.latency_ms, turnstile_ok=ts_ok, model=config.BEDROCK_MODEL)
    if r.outcome == "offline":
        return JSONResponse({"answer": r.answer, "outcome": "declined", "citations": [],
                             "session_id": session_id}, status_code=503)
    return {"answer": r.answer,
            "outcome": "answered" if r.outcome == "answered" else "declined",
            "citations": r.citations, "session_id": session_id}

@app.get("/eval/latest")
def eval_latest():
    files = sorted(HISTORY_DIR.glob("*.json"))
    if not files:
        raise HTTPException(status_code=404, detail="No eval runs yet.")
    return json.loads(files[-1].read_text())

_basic = HTTPBasic()
def require_stats_auth(creds: HTTPBasicCredentials = Depends(_basic)):
    if not config.STATS_PASSWORD or not secrets.compare_digest(creds.password, config.STATS_PASSWORD):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})

@app.get("/stats", dependencies=[Depends(require_stats_auth)])
def stats(days: int = 7, limit: int = 100):
    """Private: recent questions and outcomes, for finding new golden queries and abuse."""
    with db.connect() as conn:
        summary = conn.execute(
            """SELECT date_trunc('day', ts AT TIME ZONE %s)::date AS day, outcome, count(*), sum(cost_usd)
               FROM analytics.queries WHERE ts >= now() - (%s || ' days')::interval
               GROUP BY 1, 2 ORDER BY 1 DESC, 2""", (config.LOCAL_TZ, days)).fetchall()
        recent = conn.execute(
            """SELECT ts, outcome, question, cited, cost_usd, latency_ms FROM analytics.queries
               ORDER BY ts DESC LIMIT %s""", (limit,)).fetchall()
    return {
        "by_day": [{"day": str(d), "outcome": o, "n": n, "cost_usd": float(c or 0)} for d, o, n, c in summary],
        "recent": [{"ts": t.isoformat(), "outcome": o, "question": q, "cited": c, "cost_usd": float(cu or 0),
                    "latency_ms": ms} for t, o, q, c, cu, ms in recent],
    }
