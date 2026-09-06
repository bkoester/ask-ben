from pathlib import Path
from askben.corpus import load_corpus
from askben.config import cost_usd
from askben.llm import strip_citations

def test_load_corpus_skips_private(tmp_path: Path):
    (tmp_path / "a.md").write_text("---\nquestion: Q\ntopic: t\npublic: true\n---\nBody.")
    (tmp_path / "b.md").write_text("---\nquestion: Q2\npublic: false\n---\nHidden.")
    (tmp_path / "README.md").write_text("ignored")
    docs = load_corpus(tmp_path)
    assert [d.slug for d in docs] == ["a"]
    assert docs[0].embed_text.startswith("Q\n\nBody.")

def test_cost_matches_haiku_list_price():
    assert abs(cost_usd(2_400, 200) - 0.0034) < 1e-9

def test_strip_citations():
    assert strip_citations("Ben argues X [a1-slug]. Also Y [b2-x].") == "Ben argues X. Also Y."
