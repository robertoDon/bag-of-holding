# agent-costs

What each Claude Code agent costs. Every time a subagent finishes, and every time the
main session ends a turn, a hook writes one line with that agent's tokens and dollars.
A skill turns those lines into one table: by agent type, orchestrator vs workers, top
sessions, project, model, day or week.

Python 3 standard library only. The hooks run async and never block or fail a session.

## Install

```bash
/plugin marketplace add robertoDon/claude-plugins
/plugin install agent-costs@robertodon-plugins
```

Or from a local clone, scoped to one project:

```bash
claude plugin marketplace add ./claude-plugins --scope project
claude plugin install agent-costs@robertodon-plugins --scope project
```

Hooks load when a session starts: restart open sessions after installing.

## What it records

One JSON line per agent end in `~/.claude/agent-costs/usage.jsonl` (set
`AGENT_COSTS_DIR` to move it):

```json
{"ts": "2026-10-02T14:03:11Z", "project": "my-app", "session": "8b36…", "agent": "Explore",
 "agent_id": "a9435…", "model": "claude-sonnet-5-5", "input": 12, "output": 2210,
 "cache_read": 48113, "cache_write_5m": 9120, "cache_write_1h": 0, "usd": 0.0538,
 "duration_ms": 41200, "turns": 6, "tool_calls": 9}
```

- `agent` is the subagent type, or `main` for the session itself.
- `turns` counts API calls; `project` is the name of the git root of the session's cwd.
- Each turn of the main session records only what came since the last record, and a
  resumed subagent only its new messages. Nothing is counted twice.

What it never records: prompts, responses, tool inputs or outputs, file names, paths.

## Prices

`prices.json` holds USD per million tokens per model, with the date it was read from
Anthropic's pricing page. Cache reads and both cache-write TTLs have their own rates.
Fast mode and US-only inference multipliers apply when the transcript says so.

Override or add a model in `~/.claude/agent-costs/prices.json`, same shape:

```json
{"models": {"claude-new-model": {"input": 3, "output": 15, "cache_read": 0.3,
                                 "cache_write_5m": 3.75, "cache_write_1h": 6}}}
```

A model with no price is never guessed: its line has `"usd": null` and
`"unpriced": [...]`, and the report flags it.

## Report

Ask Claude "what did agents cost this week?" (the `cost-report` skill), or run it:

```bash
python3 plugins/agent-costs/scripts/agent_costs.py report --by agent --days 7
```

```
Last 7 days: $41.27 total · orchestrator (main) $29.80 (72%) · workers $11.47 (28%) · 213 runs

| agent | runs | turns | tokens | cache hit | usd | share |
|---|---:|---:|---:|---:|---:|---:|
| main | 64 | 1122 | 61.4M | 97% | $29.80 | 72% |
| Explore | 58 | 640 | 9.8M | 88% | $6.12 | 15% |
| general-purpose | 41 | 512 | 6.0M | 85% | $4.03 | 10% |
| Plan | 50 | 208 | 2.1M | 90% | $1.32 | 3% |
```

`--by project|session|model|day|week`, `--days N` (0 = all), `--project NAME`, `--top N`.

Hook errors go to `~/.claude/agent-costs/hook.log`.

## Tests

```bash
python3 -m unittest discover plugins/agent-costs/tests
```
