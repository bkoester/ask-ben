"""Postgres + pgvector. Two schemas: `corpus` (documents + vectors) and `analytics` (one row per query).

The analytics schema is the store PLAN.md §7 describes; the daily spend cap reads from it.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg
from pgvector.psycopg import register_vector
from . import config

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS corpus;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS corpus.documents (
  slug         text PRIMARY KEY,
  title        text NOT NULL,
  topic        text NOT NULL DEFAULT '',
  body         text NOT NULL,
  updated      text NOT NULL DEFAULT '',
  content_hash text NOT NULL,
  embedding    vector({config.EMBEDDING_DIM}) NOT NULL,
  embedded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analytics.queries (
  id            bigserial PRIMARY KEY,
  ts            timestamptz NOT NULL DEFAULT now(),
  session_id    text,
  ip_hash       text,
  question      text NOT NULL,
  answer        text,
  outcome       text NOT NULL,   -- answered | declined-off-limits | declined-no-source | rate-limited | offline
  retrieved     jsonb,           -- [{{slug, score}}]
  cited         jsonb,           -- [slug]
  input_tokens  int NOT NULL DEFAULT 0,
  output_tokens int NOT NULL DEFAULT 0,
  cost_usd      numeric(10,6) NOT NULL DEFAULT 0,
  latency_ms    int,
  turnstile_ok  boolean,
  model         text,
  feedback      smallint         -- +1 / -1 / null
);
CREATE INDEX IF NOT EXISTS queries_ts_idx ON analytics.queries (ts);
"""

@contextmanager
def connect():
    with psycopg.connect(config.DATABASE_URL) as conn:
        register_vector(conn)
        yield conn

def init_schema() -> None:
    """Idempotent. Plain connect (no vector adapter) because the extension may not exist yet."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()

def init_schema_with_retry(attempts: int = 10, delay_s: float = 3.0) -> bool:
    """Postgres may still be starting when the API comes up; try for ~30 s, then give up quietly.
    /health keeps reporting the real state either way."""
    import time
    for i in range(attempts):
        try:
            init_schema()
            return True
        except Exception:
            if i == attempts - 1:
                return False
            time.sleep(delay_s)
    return False

def local_day_start() -> datetime:
    tz = ZoneInfo(config.LOCAL_TZ)
    now = datetime.now(tz)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def spend_today_usd(conn) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM analytics.queries WHERE ts >= %s",
        (local_day_start(),),
    ).fetchone()
    return float(row[0])

def log_query(conn, **row) -> None:
    cols = ", ".join(row.keys())
    vals = ", ".join(["%s"] * len(row))
    conn.execute(f"INSERT INTO analytics.queries ({cols}) VALUES ({vals})", tuple(row.values()))
    conn.commit()
