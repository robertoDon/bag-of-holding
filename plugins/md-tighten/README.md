<p align="center">
  <img src="assets/logo.svg" width="220" alt="md-tighten: a page cinched with a belt, stamped NO FACT LOST">
</p>

<h1 align="center">md-tighten</h1>

<p align="center">
  <em>Same facts. Fewer words.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude%20Code-plugin-111111?style=flat-square" alt="Claude Code plugin">
  <img src="https://img.shields.io/badge/python-stdlib%20only-111111?style=flat-square" alt="Python stdlib only">
  <img src="https://img.shields.io/badge/dependencies-0-111111?style=flat-square" alt="Zero dependencies">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
  <strong>61% fewer prose bytes on bloated docs &middot; 39/39 planted facts kept &middot; two checks before any delivery</strong>
</p>

---

Your CLAUDE.md is 400 lines. Half of it says the same thing twice.

Ask a model to "make it shorter" and it will. It also drops the one "unless" that mattered.
md-tighten cuts the words, then proves the facts are still there.

## Before / after

Before, 95 words:

> If at any point the error rate goes above 0.5%, you should roll back right away. Do not
> wait to see if it recovers on its own, because in our experience it usually does not. To
> roll back, run `./scripts/rollback.sh --to previous`, which restores the previous version.
>
> After you roll back, you should page the on-call engineer through the #ops-oncall channel
> so that they are aware of the situation and can help investigate. The only exception to
> this is a docs-only change: if your change only touched documentation, you do not need to
> page anyone.

After, 27 words:

> - Error rate above 0.5%: roll back immediately.
> - Roll back with `./scripts/rollback.sh --to previous`.
> - After rollback, page the on-call engineer via `#ops-oncall`.
> - Exception: docs-only changes don't need paging.

Same threshold, same command, same channel, same exception.

## Numbers

One real headless run over three bloated test docs, each with planted facts:

| doc | prose bytes | cut | planted facts | rounds |
|---|--:|--:|--:|--:|
| deploy runbook, English | 3690 → 1337 | 63.8% | 14/14 | 3 |
| data ingestion guide, Portuguese | 2768 → 1134 | 59.0% | 14/14 | 2 |
| API limits, table + code + front matter | 2278 → 915 | 59.8% | 11/11 | 2 |

Every doc failed the fact check at least once: a softened "never", a dropped reason with a number.
Each came back fixed, still far past the 25% target.

On a doc that was already tight, it cut 4.8% and stopped. It listed the facts that blocked a deeper cut.
The prompt it grew from cut 6.4% of the same doc and lost 3 facts.

## How it works

```
snapshot → editor rewrites → literal check → fact check (fresh agent) → done
                ↑                  │ fail            │ absent
                └── problem list ──┴─────────────────┘
          3 rounds max. Still failing: the original comes back.
```

- **Literal check** (`scripts/check_literals.py`). Every number, unit, date, path, URL, flag,
  inline code, email, `#channel`, CAPS or CamelCase name and snake_case id of the before is
  in the after. Code block contents and front matter are unchanged. No table loses a row.
- **Fact check** (`fact-checker` agent). It never saw the edit. It lists every rule and fact
  of the before, then marks each present or absent in the after. A softened "never", a dropped
  "unless" or a widened scope counts as absent.
- **The cut** is measured in prose bytes (`scripts/prose_bytes.py`). Code, tables and front
  matter are frozen, so they can't be traded for budget. Swapped punctuation and flattened
  tables don't count.

Can't hit the target without losing a fact? It stops short and says by how much, and why.
An honest miss beats a cosmetic hit.

## Install

```
/plugin marketplace add robertoDon/bag-of-holding
```
```
/plugin install md-tighten@robertodon-plugins
```

Send them as two separate prompts. Needs `python3` on the `PATH`.

## Use

```
/md-tighten:tighten docs/runbook.md
/md-tighten:tighten docs/ target 40%
/md-tighten:tighten docs/ owners: README.md = overview, install; docs/usage.md = commands, flags
```

- A file, or a folder: every `*.md` under it, hidden folders skipped.
- Default target: 25% fewer prose bytes per document.
- Owners mode: the named files are edited together, each sentence moved to the file that owns it.
- Writes in the document's language. Portuguese stays Portuguese.
- Edits in place. Originals go to `.md-tighten-snapshot/`, ready for `diff -r`.

## Tests

```bash
python3 -m unittest discover plugins/md-tighten/tests
python3 plugins/md-tighten/tests/eval_planted.py plugins/md-tighten/tests/fixtures <tightened copies>
```

Forty-two tests on both scripts: tables with and without pipes, fenced and indented code,
nested lists, front matter, unit synonyms, repeated code blocks. The literal check raised zero
false alarms on 2,500 real docs checked against themselves.

## License

MIT
