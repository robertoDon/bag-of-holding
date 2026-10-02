---
name: cost-report
description: Show what Claude Code agents cost - dollars and tokens by agent type, orchestrator (main session) vs workers (subagents), top sessions, by project, model, day or week - from the usage the agent-costs hooks record. Triggers: "how much did agents cost", "cost by agent", "which subagent is expensive", "cost this week", "top sessions by cost".
---

# Cost report

Run the report script that ships with this plugin. It sits two directories above this
skill's base directory:

```bash
python3 "<this skill's base directory>/../../scripts/agent_costs.py" report --by agent --days 7
```

Pick the flags from the question:

- `--by agent` (default): cost per agent type; the header already splits orchestrator
  (`main`) vs workers.
- `--by session --top 10`: top sessions.
- `--by project`, `--by model`.
- `--by day` or `--by week`: over time.
- `--days N` sets the window (`--days 0` is all time); `--project NAME` narrows it.

Show the script's output as is: one header line and one table. Add at most one line of
reading (the biggest cost, or an unpriced model if the header lists one). An unpriced
model has no rate in `prices.json`; the user can add it to `~/.claude/agent-costs/prices.json`.
