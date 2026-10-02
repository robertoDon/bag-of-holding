<h1 align="center">agent-costs</h1>

<p align="center">
  <em>Every agent sends a bill. Now you can read it.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude%20Code-plugin-111111?style=flat-square" alt="Claude Code plugin">
  <img src="https://img.shields.io/badge/python-stdlib%20only-111111?style=flat-square" alt="Python stdlib only">
  <img src="https://img.shields.io/badge/dependencies-0-111111?style=flat-square" alt="Zero dependencies">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
  <strong>Within 0.03% of the books on real runs &middot; nothing counted twice &middot; zero content stored</strong>
</p>

---

You spawned twelve subagents. The session cost $43. Which one ate it?

Claude Code tells you the total. agent-costs tells you who spent it.

## Before / after

Before:

```
/cost
Total cost: $43.12
```

After, "what did agents cost this week?":

```
Last 7 days: $41.27 total · orchestrator (main) $29.80 (72%) · workers $11.47 (28%) · 213 runs

| agent           | runs | turns | tokens | cache hit |    usd | share |
|-----------------|-----:|------:|-------:|----------:|-------:|------:|
| main            |   64 |  1122 |  61.4M |       97% | $29.80 |   72% |
| Explore         |   58 |   640 |   9.8M |       88% |  $6.12 |   15% |
| general-purpose |   41 |   512 |   6.0M |       85% |  $4.03 |   10% |
| Plan            |   50 |   208 |   2.1M |       90% |  $1.32 |    3% |
```

One table. By agent, project, session, model, day or week.

## Numbers

Checked against independently closed books, not against itself:

| check | agent-costs | reference | diff |
|---|--:|--:|--:|
| closed run, Haiku 4.5 workers | $0.9713 | $0.9714 | -0.01% |
| closed run, Haiku 4.5 workers | $1.1397 | $1.1395 | +0.02% |
| closed run, Sonnet 5.5 workers | $1.2715 | $1.2719 | -0.03% |
| headless session, same model, vs Claude Code's own figure | $0.04895 | $0.04895 | 0% |

Claude Code's session total runs about $0.001 higher, for a small internal call that is in no transcript.

Resumed and forked sessions copy old messages into new transcripts. On one real machine, 538 message ids appeared in more than one of 680 transcripts. Each is billed once.

## How it works

```
subagent finishes   → SubagentStop hook → bill that agent's transcript
main turn ends      → Stop hook         → bill only what's new since the last turn
session closes      → SessionEnd hook   → catch whatever is left
```

- One JSON line per agent end, in `~/.claude/agent-costs/usage.jsonl`.
- Messages are grouped by id, so a streamed message split over several lines counts once, at its final usage.
- A per-transcript offset means each turn bills only its growth.
- Hooks log errors to `hook.log` and never fail a session.

```json
{"ts": "2026-10-02T14:03:11Z", "project": "my-app", "session": "8b36…", "agent": "Explore",
 "agent_id": "a9435…", "model": "claude-sonnet-5-5", "input": 12, "output": 2210,
 "cache_read": 48113, "cache_write_5m": 9120, "cache_write_1h": 0, "usd": 0.0538,
 "duration_ms": 41200, "turns": 6, "tool_calls": 9}
```

**Never stored:** prompts, responses, tool inputs or outputs, file names, paths. Only numbers and agent names.

## Prices

`prices.json` holds USD per million tokens per model, and the date it was read from [Anthropic's pricing page](https://platform.claude.com/docs/en/about-claude/pricing).

- Cache reads, 5-minute writes and 1-hour writes each get their own rate. Not every model reads at 0.1x: Opus 5.5 reads at 0.05x.
- Fast mode and US-only inference multipliers apply when the transcript says so.
- An unknown model is never guessed. Its line gets `"usd": null`, and the report flags it.

Override or add a model in `~/.claude/agent-costs/prices.json`:

```json
{"models": {"claude-new-model": {"input": 3, "output": 15, "cache_read": 0.3,
                                 "cache_write_5m": 3.75, "cache_write_1h": 6}}}
```

## Install

```
/plugin marketplace add robertoDon/claude-plugins
```
```
/plugin install agent-costs@robertodon-plugins
```

Send them as two separate prompts, then restart open sessions: hooks load at start-up.

## Report

Ask Claude in plain words, or run it yourself:

```bash
python3 plugins/agent-costs/scripts/agent_costs.py report --by agent --days 7
```

`--by agent|project|session|model|day|week` · `--days N` (0 = all) · `--project NAME` · `--top N`

Data lives in `~/.claude/agent-costs/`. Set `AGENT_COSTS_DIR` to move it.

## Tests

```bash
python3 -m unittest discover plugins/agent-costs/tests
```

Fourteen tests on hand-built transcripts: split messages, resumed agents, forked sessions, truncated files, unpriced models, broken overrides.

## License

MIT
