# agent-costs: plan

Goal: one usage line per agent end (subagent or main-session turn), priced, no content.
Then a one-table report.

## Shape

- `hooks/hooks.json`: `SubagentStop` and `Stop`, both `async`, both call
  `scripts/agent_costs.py record`. The script never exits non-zero and never prints.
- `scripts/agent_costs.py`: one stdlib module.
  - `record`: reads the hook payload, finds the transcript (the subagent's own file under
    `<session>/subagents/`, or the main transcript), reads only what was appended since
    the last record, prices it, appends one line to `~/.claude/agent-costs/usage.jsonl`.
  - `report`: groups the lines by agent type, project, session, day or week.
- `prices.json`: USD per MTok per model, with the date it was read. A user file
  `~/.claude/agent-costs/prices.json` overrides per model.
- `skills/cost-report/SKILL.md`: runs `report` and shows the table.

## Counting rules

- One API call = one assistant `message.id`. A transcript writes one line per content
  block, each repeating the id; usage grows across those lines (output tokens are
  final only on the last). Group by id, take the per-field max.
- Never twice: a per-transcript state file holds the byte offset already read and the
  ids already billed. A resumed subagent or the next main turn bills only the new
  messages. Sidechain lines in a main transcript are skipped (the subagent hook bills
  them).
- Partial last line (truncated or mid-write): not consumed; the offset stops before it.
- A model with no price: `usd` is null, `unpriced` lists it, the report shows it apart.
  No guessing.
- `<synthetic>` and zero-token messages cost nothing and are not "unpriced".
- Fast mode (`usage.speed == "fast"`) multiplies the model's rates by its
  `fast_multiplier`; `inference_geo == "us"` multiplies by 1.1.

## What a line holds

ts, project (git root name), session, agent_type (`main` for the session), agent_id,
model, tokens {input, output, cache_read, cache_write_5m, cache_write_1h}, usd,
unpriced, duration_ms, turns (API calls), tool_calls. Nothing else.

## Tests

- Hand-built transcripts: simple subagent, subagent with cache, multi-turn main
  session (second record bills only the delta), unpriced model, truncated transcript.
- Real-number check: three closed runs of a real multi-agent pipeline, plugin cost vs its own cost
  index, by script.
- Headless: project-scope install from the local marketplace, one `claude -p` that
  spawns a subagent, check two lines and the report.
