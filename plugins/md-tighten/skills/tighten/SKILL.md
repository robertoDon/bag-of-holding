---
name: tighten
description: Rewrite bloated Markdown into short sentences, bullets and tables without losing a fact. Takes a file or a folder. Edits in place, then gates every document on two checks: a script that every literal survived, and an independent agent that every fact and rule survived. Restores the original when it can't pass both. Use when docs, READMEs, agent prompts or CLAUDE.md files have grown wordy.
argument-hint: <file-or-folder> [target 25%] [owners: file = what it owns; ...]
allowed-tools: Read, Glob, Grep, Agent, Bash(python3 *), Bash(mktemp *), Bash(mkdir *), Bash(cp *)
---

# Tighten Markdown

Request: $ARGUMENTS

You orchestrate. The `md-tighten:editor` agent rewrites; the `md-tighten:fact-checker`
agent audits. You never edit a document yourself.

Scripts (if the variable below is not expanded, Glob `**/md-tighten/scripts/*.py`):

- Meter: `${CLAUDE_PLUGIN_ROOT}/scripts/prose_bytes.py`
- Literal check: `${CLAUDE_PLUGIN_ROOT}/scripts/check_literals.py`

## 1. Read the request

- **Paths.** A file, or a folder: every `*.md` under it.
  Skip `.git`, `node_modules`, `vendor`, `dist`, `build` and hidden folders.
- **Target.** Percent cut in prose bytes. Default 25%.
- **Owners.** Optional. The user says which file owns what ("README.md = overview,
  install; docs/usage.md = flags"). Those files form one unit, edited together.
  Without owners, each document is its own unit and nothing moves between files.
- Nothing found? Say so and stop.

## 2. Snapshot and measure

- Run `mktemp -d` on its own. Shell variables don't survive between calls: reuse the printed path literally.
- Copy every document to `<snapshot dir>/<its path relative to the request root>`, with `mkdir -p`.
- Run the meter on the originals. Skip a document under 400 prose bytes; report it as too short.

## 3. Rounds, per unit

Run up to 4 units at a time: launch their agents in one message.
Each unit gets at most 3 rounds.

**a. Edit.** Launch `md-tighten:editor` with:

- the document path(s) and their snapshot path(s);
- the target, and the meter and literal-check paths;
- the owners map, in owners mode;
- on round 2+, the exact problem lines from the failed check below.

**b. Literal check.** `python3 <check_literals> <snapshot> <doc>`, or
`--before <snapshots…> --after <docs…>` for an owners unit.
Exit 1 → next round with its output. Skip c this round.

**c. Fact check.** Launch a **new** `md-tighten:fact-checker` every round, never a resumed one.
Give it only the BEFORE (snapshot) and AFTER (document) paths. No editor output, no history.
`VERDICT: FAIL` → next round with its ABSENT and ADDED lines.

**d. Both pass** → the unit is done.

After round 3 with a check still failing: copy the snapshot back over the document.
Status: restored. A document that lost a fact is never delivered.

## 4. Report

Run the meter's `--compare` per document. Then one table:

| Document | Prose before → after | Cut | Literals | Facts | Rounds | Status |
| --- | --- | --- | --- | --- | --- | --- |

- Status: `done`, `under target`, `restored` or `too short`.
- Under target: say by how many bytes, and the editor's BLOCKERS line.
- Restored: the problem lines that never cleared.
- Last line: the snapshot folder, for `diff -r`.
