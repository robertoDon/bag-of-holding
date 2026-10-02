# md-tighten — plan

Rewrite bloated Markdown into short sentences, bullets and tables. Lose no fact.

## Pieces

| Piece | Path | Job |
| --- | --- | --- |
| Skill | `skills/tighten/SKILL.md` | Takes a file or folder. Snapshots, dispatches, gates, restores. |
| Editor agent | `agents/editor.md` | Reshapes and cuts. Measures itself with the meter. |
| Fact-checker agent | `agents/fact-checker.md` | Fresh context. Lists facts of the before, marks each in the after. |
| Meter | `scripts/prose_bytes.py` | Prose bytes vs frozen bytes (code fences, tables, front matter). |
| Literal check | `scripts/check_literals.py` | Every literal of the before is in the after. Exit 1 lists what's missing. |

## The gate

1. Snapshot the original to a temp dir.
2. Editor rewrites in place.
3. Literal check. Fail → back to the editor with the list.
4. Fact-checker on snapshot vs file. Any absent → back to the editor.
5. Max 3 rounds. Still failing → restore the original, report why.
6. Under target is allowed. Report the shortfall and the blocking rules.

## Generalized from the source agent

- Four-file routing → optional owners mode: the user names which file owns what.
- Per-file budgets → one default target per document: 25% of prose bytes, overridable.
- Anti-gaming rules kept: no punctuation swaps, no flattened tables, no dropped literals, an honest miss beats a cosmetic hit.
- Writes in the document's language.

## Tests

- Unit tests for both scripts: tables, fences, nested lists, front matter.
- Three bloated fixtures with planted facts (EN, PT, table+code). Run the real plugin headless, measure the cut, check every planted fact.
- One real doc, on a copy, against the source agent's output.
- Install from the local marketplace headless; check the prefixed skill and agents load.
