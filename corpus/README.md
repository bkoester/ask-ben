# corpus/

One Markdown file per published answer. **Everything here is public the moment it is
committed**, so nothing lands here until Ben has approved it for publication (drafts stay in
the private ideas folder).

```markdown
---
question: "How does Ben decide which chatbot failures matter?"
topic: evaluation
public: true
updated: 2026-09-05
---

The answer, 150–400 words, written for a stranger and a coworker alike.
```

`public: false` keeps a file out of the index. File name = slug = what the bot cites.
Run `python -m askben.ingest` after any change; only changed files are re-embedded.
