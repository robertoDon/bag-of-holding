# md-tighten

Rewrites bloated Markdown into short sentences, bullets and tables. Loses no fact.

## Install

```
/plugin marketplace add robertoDon/claude-plugins
/plugin install md-tighten@robertodon-plugins
```

Python 3 on the `PATH`. No other dependency.

## Use

```
/md-tighten:tighten docs/runbook.md
/md-tighten:tighten docs/ target 40%
/md-tighten:tighten docs/ owners: README.md = overview, install; docs/usage.md = commands, flags
```

- A file, or a folder (every `*.md` under it, hidden folders skipped).
- Default target: 25% fewer prose bytes per document.
- Owners mode: the files you name are edited together, each sentence moved to its owner.
- Writes in the document's language. Edits in place; originals go to `.md-tighten-snapshot/`.

## What it guarantees

A document is delivered only when both checks pass:

- **Literal check** (`scripts/check_literals.py`). Every number, unit, date, path, URL, flag,
  inline code, email, `#channel`, CAPS or CamelCase name and snake_case id of the before is
  in the after. Code block contents and front matter are unchanged. No table loses a row.
- **Fact check** (`fact-checker` agent). A fresh agent that never saw the edit lists every
  rule and fact of the before, then marks each present or absent in the after. A softened
  "never", a dropped "unless" or a widened scope counts as absent.

Either fails: the editor gets the list and tries again, up to 3 rounds. Still failing:
the original is restored. Can't hit the target without losing a fact: it stops short and
says by how much, and which facts blocked it.

The cut is measured on prose bytes only (`scripts/prose_bytes.py`). Code, tables and front
matter are frozen, so they can't be traded for budget. Swapping punctuation and flattening
tables don't count either.

## Before and after

From the test fixtures, one real run:

> ## If something goes wrong
>
> If at any point the error rate goes above 0.5%, you should roll back right away. Do not
> wait to see if it recovers on its own, because in our experience it usually does not. To
> roll back, run `./scripts/rollback.sh --to previous`, which restores the previous version.
>
> After you roll back, you should page the on-call engineer through the #ops-oncall channel
> so that they are aware of the situation and can help investigate. The only exception to
> this is a docs-only change: if your change only touched documentation, you do not need to
> page anyone.

> ## If something goes wrong
>
> - Error rate above 0.5%: roll back immediately.
> - Roll back with `./scripts/rollback.sh --to previous`.
> - After rollback, page the on-call engineer via `#ops-oncall`.
> - Exception: docs-only changes don't need paging.

Three bloated test docs (English, Portuguese, tables and code): 61% fewer prose bytes on
average, 39 of 39 planted facts kept. The fact check sent all three back at least once.

On a doc that was already tight, it cut 4.8% and stopped, listing what blocked it.

## Tests

```
python3 -m unittest discover tests
python3 tests/eval_planted.py tests/fixtures <folder with the tightened copies>
```

## License

MIT
