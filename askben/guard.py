"""Deterministic off-limits check. Loaded from policy.yaml."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
import yaml

POLICY_PATH = Path(__file__).with_name("policy.yaml")

@dataclass(frozen=True)
class Policy:
    decline_sentence: str
    no_source_sentence: str
    offline_sentence: str
    rules: tuple[tuple[str, tuple[re.Pattern, ...]], ...]

    def match(self, question: str) -> str | None:
        """Return the name of the first off-limits rule the question trips, else None."""
        for name, pats in self.rules:
            if any(p.search(question) for p in pats):
                return name
        return None

def load_policy(path: Path = POLICY_PATH) -> Policy:
    raw = yaml.safe_load(path.read_text())
    rules = tuple(
        (r["name"], tuple(re.compile(p, re.IGNORECASE) for p in r["patterns"]))
        for r in raw.get("off_limits", [])
    )
    return Policy(
        decline_sentence=raw["decline_sentence"].strip(),
        no_source_sentence=raw["no_source_sentence"].strip(),
        offline_sentence=raw["offline_sentence"].strip(),
        rules=rules,
    )
