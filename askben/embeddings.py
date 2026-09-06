"""Amazon Titan Text Embeddings v2 on Bedrock, via the instance role. No API key.

Titan v2 embeds one text per InvokeModel call; the corpus is small enough that a loop is fine.
`normalize=True` returns unit vectors so cosine distance in pgvector is exact.
"""
from __future__ import annotations
import json
import boto3
from . import config

_client = None
def client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=config.BEDROCK_REGION)
    return _client

def embed(texts: list[str], task: str = "") -> list[list[float]]:
    """`task` is accepted for call-site compatibility; Titan has no query/passage modes."""
    out: list[list[float]] = []
    for text in texts:
        resp = client().invoke_model(
            modelId=config.EMBEDDING_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": config.EMBEDDING_DIM, "normalize": True}),
        )
        out.append(json.loads(resp["body"].read())["embedding"])
    return out
