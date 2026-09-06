"""All configuration from the environment. See .env.example for meaning and defaults."""
import os

def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://askben:askben@localhost:5433/askben")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIM = 1024  # Titan v2 supports 1024 / 512 / 256

BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-2")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_JUDGE_MODEL = os.getenv("BEDROCK_JUDGE_MODEL", BEDROCK_MODEL)

ENABLED = _bool("ENABLED", True)
DAILY_SPEND_CAP_USD = float(os.getenv("DAILY_SPEND_CAP_USD", "1.00"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))
TOP_K = int(os.getenv("TOP_K", "4"))
RATE_LIMIT_PER_10MIN = int(os.getenv("RATE_LIMIT_PER_10MIN", "12"))
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "300"))

TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET", "")
IP_HASH_SALT = os.getenv("IP_HASH_SALT", "change-me")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
# Regex for preview origins, e.g. ^https://([a-z0-9-]+\.)?benkoester\.pages\.dev$ (empty = none)
ALLOWED_ORIGIN_REGEX = os.getenv("ALLOWED_ORIGIN_REGEX", "") or None
CITATION_BASE = os.getenv("CITATION_BASE", "https://github.com/bkoester/ask-ben/blob/main/corpus").rstrip("/")
STATS_PASSWORD = os.getenv("STATS_PASSWORD", "")

# Local day boundary for the spend cap and the stats endpoint.
LOCAL_TZ = os.getenv("LOCAL_TZ", "America/Detroit")

# Haiku 4.5 list price, USD per million tokens (Anthropic pricing page, 2026-09-05;
# Bedrock global endpoints match, regional add 10%). Used for the cost column and the cap.
PRICE_IN_PER_MTOK = float(os.getenv("PRICE_IN_PER_MTOK", "1.00"))
PRICE_OUT_PER_MTOK = float(os.getenv("PRICE_OUT_PER_MTOK", "5.00"))

def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_IN_PER_MTOK + output_tokens * PRICE_OUT_PER_MTOK) / 1_000_000
