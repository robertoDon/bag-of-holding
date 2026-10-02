#!/usr/bin/env python3
"""What each Claude Code agent costs: one usage line per agent end, and a report.

    agent_costs.py record subagent|main   < hook payload on stdin  (the hooks call this)
    agent_costs.py report [--by agent|project|session|model|day|week] [--days N]

Lines go to ~/.claude/agent-costs/usage.jsonl (or $AGENT_COSTS_DIR). They hold numbers
and agent names only: no prompt, no response, no file name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import fcntl
    msvcrt = None
except ImportError:  # Windows
    fcntl = None
    import msvcrt

HERE = Path(__file__).resolve().parent
BUNDLED_PRICES = HERE.parent / "prices.json"
TOKENS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")
GEO_US = 1.1


def data_dir() -> Path:
    return Path(os.environ.get("AGENT_COSTS_DIR") or Path.home() / ".claude" / "agent-costs")


# ---------------------------------------------------------------- prices

def load_prices(user_file: Path | None = None) -> dict:
    """Bundled table, overridden field by field by the user's own file. A user file that
    does not parse is logged and ignored: it must not stop the recording."""
    models = json.loads(BUNDLED_PRICES.read_text())["models"]
    user_file = user_file or data_dir() / "prices.json"
    if user_file.is_file():
        try:
            for model, rate in json.loads(user_file.read_text()).get("models", {}).items():
                models[model] = {**models.get(model, {}), **rate}
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            log(f"ignored {user_file}: {exc}")
    return models


def rate_for(model: str, prices: dict) -> dict | None:
    """Exact id, else the id without a `[1m]`-style tag or a -YYYYMMDD snapshot date.
    A rate missing any of the five classes counts as no rate: never a guess."""
    rate = prices.get(model) or prices.get(re.sub(r"-\d{8}$", "", re.sub(r"\[.*\]$", "", model)))
    return rate if rate and all(isinstance(rate.get(k), (int, float)) for k in TOKENS) else None


def usage_tokens(usage: dict) -> dict[str, int]:
    """The five billed classes from one API usage object. A flat
    cache_creation_input_tokens with no TTL split is taken as the 5m write."""
    ttl = usage.get("cache_creation") or {}
    flat = usage.get("cache_creation_input_tokens") or 0
    w5 = ttl.get("ephemeral_5m_input_tokens", 0) if ttl else flat
    w1 = ttl.get("ephemeral_1h_input_tokens", 0) if ttl else 0
    return {"input": usage.get("input_tokens") or 0,
            "output": usage.get("output_tokens") or 0,
            "cache_read": usage.get("cache_read_input_tokens") or 0,
            "cache_write_5m": w5 or 0, "cache_write_1h": w1 or 0}


def cost(tokens: dict, rate: dict, fast: bool = False, geo_us: bool = False) -> float:
    mult = (rate.get("fast_multiplier", 1) if fast else 1) * (GEO_US if geo_us else 1)
    return sum(tokens[k] * rate[k] for k in TOKENS) * mult / 1_000_000


# ---------------------------------------------------------------- transcripts

def read_new(path: Path, offset: int) -> tuple[list[dict], int]:
    """Complete JSON lines appended since `offset`, and the new offset. A last line with
    no newline (truncated, or still being written) is left for the next read."""
    size = path.stat().st_size
    if offset > size:          # rewritten in place: skip it rather than bill it twice
        return [], size
    with path.open("rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1
    rows = []
    for raw in data[:end].splitlines():
        try:
            rows.append(json.loads(raw))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return rows, offset + end


def bill(rows: list[dict], tail: dict, prices: dict, skip_sidechain: bool,
         skip_ids: set | frozenset = frozenset()) -> tuple[dict, dict]:
    """Price the new rows. One API call is one assistant message id; the transcript
    repeats the id on every content-block line and its usage grows across them (output
    is final only on the last), so take the per-field max. `tail` is what earlier records
    already billed for the last ids they saw: only the growth is billed again, so a
    message split across two records is neither lost nor counted twice."""
    msgs: dict[str, dict] = {}
    tool_ids: set[str] = set()
    first_ts = last_ts = None
    for n, row in enumerate(rows):
        if skip_sidechain and row.get("isSidechain"):
            continue
        ts = row.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        msg = row.get("message") or {}
        if row.get("type") != "assistant" and msg.get("role") != "assistant":
            continue
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_ids.add(block.get("id") or f"line{n}")
        usage = msg.get("usage")
        if not usage:
            continue
        mid = msg.get("id") or f"\x00line{n}"
        if mid in skip_ids:
            continue
        m = msgs.setdefault(mid, {"model": None, "fast": False, "us": False,
                                  "tok": dict.fromkeys(TOKENS, 0)})
        m["model"] = m["model"] or msg.get("model") or "unknown"
        m["fast"] = m["fast"] or usage.get("speed") == "fast"
        m["us"] = m["us"] or usage.get("inference_geo") == "us"
        for k, v in usage_tokens(usage).items():
            m["tok"][k] = max(m["tok"][k], v)

    tokens = dict.fromkeys(TOKENS, 0)
    by_model: dict[str, int] = defaultdict(int)
    usd, priced, unpriced, turns, new_tail = 0.0, False, set(), 0, {}
    for mid, m in msgs.items():
        before = tail.get(mid) or {}
        now = {k: max(m["tok"][k], before.get(k, 0)) for k in TOKENS}
        delta = {k: now[k] - before.get(k, 0) for k in TOKENS}
        new_tail[mid] = now
        if not any(delta.values()):
            continue
        if mid not in tail:                # a zero-usage stub is not an API call
            turns += 1
        for k in TOKENS:
            tokens[k] += delta[k]
        by_model[m["model"]] += sum(delta.values())
        rate = rate_for(m["model"], prices)
        if rate is None:
            unpriced.add(m["model"])
            continue
        usd += cost(delta, rate, m["fast"], m["us"])
        priced = True
    new_tail = new_tail or tail          # a chunk with no assistant line keeps the old tail
    start, end = _ts(first_ts), _ts(last_ts)
    out = {
        "model": max(by_model, key=by_model.get) if by_model else None,
        **tokens,
        "usd": round(usd, 6) if priced or not unpriced else None,
        "duration_ms": int((end - start).total_seconds() * 1000) if start and end else None,
        "turns": turns, "tool_calls": len(tool_ids),
    }
    if len(by_model) > 1:
        out["models"] = sorted(by_model)
    if unpriced:
        out["unpriced"] = sorted(unpriced)
    return out, new_tail


def _ts(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


# ---------------------------------------------------------------- record (the hook)

def subagent_transcript(payload: dict) -> Path | None:
    """The subagent's own file: given, or `<session>/subagents/**/agent-<id>.jsonl`
    beside the main transcript (Workflow agents sit one level down)."""
    if payload.get("agent_transcript_path"):
        return Path(payload["agent_transcript_path"])
    agent_id, main = payload.get("agent_id"), payload.get("transcript_path")
    if not agent_id or not main:
        return None
    base = Path(main).parent / str(payload.get("session_id") or Path(main).stem) / "subagents"
    return next(base.rglob(f"agent-{agent_id}.jsonl"), None)


def project_name(cwd: str | None) -> str | None:
    if not cwd:
        return None
    path = Path(cwd)
    for p in (path, *path.parents):
        if (p / ".git").exists():
            return p.name
    return path.name


def _agent_type(path: Path) -> str | None:
    meta = path.with_name(path.stem + ".meta.json")
    try:
        return json.loads(meta.read_text()).get("agentType")
    except (OSError, json.JSONDecodeError):
        return None


def _bill_file(path: Path, kind: str, agent: str, payload: dict, root: Path,
               prices: dict, now: datetime, skip_ids: set | None = None) -> list[str]:
    """Bill what one transcript gained since its last record; returns the billed ids.
    The state is saved before the line is appended: a failure in between loses a line
    rather than counting it twice."""
    state_file = root / "state" / (hashlib.sha1(str(path).encode()).hexdigest() + ".json")
    try:
        state = json.loads(state_file.read_text()) if state_file.is_file() else {}
    except json.JSONDecodeError:   # unreadable state: resume at the end, never re-bill
        state = {"offset": path.stat().st_size}
    rows, offset = read_new(path, state.get("offset", 0))
    line, tail = bill(rows, state.get("tail", {}), prices, kind == "main", skip_ids or set())
    tmp = state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps({"offset": offset, "tail": tail}))
    os.replace(tmp, state_file)
    if not (line["turns"] or any(line[k] for k in TOKENS)):
        return []
    line = {"ts": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "project": project_name(payload.get("cwd")),
            "session": payload.get("session_id"), "agent": agent,
            **({"agent_id": path.stem[len("agent-"):]} if kind == "subagent" else {}),
            **line}
    with (root / "usage.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    return [mid for mid in tail if not mid.startswith("\x00")]


def record(kind: str, payload: dict, now: datetime | None = None) -> str:
    """One hook firing. A subagent end bills that subagent's file. A main-session end
    bills the main transcript, then catches up every subagent file already recorded once
    (a final line flushed after its own hook read the file, or a resumed agent)."""
    main = Path(payload["transcript_path"]) if payload.get("transcript_path") else None
    path = subagent_transcript(payload) if kind == "subagent" else main
    if path is None or not path.is_file():
        return f"ignored {kind}: no transcript ({sorted(payload)})"
    now = now or datetime.now(timezone.utc)
    root = data_dir()
    (root / "state").mkdir(parents=True, exist_ok=True)
    prices = load_prices()
    with (root / ".lock").open("a") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        else:
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        if kind == "subagent":
            agent = payload.get("agent_type") or _agent_type(path) or "subagent"
            _bill_file(path, kind, agent, payload, root, prices, now)
            return ""
        # A resumed or forked session copies earlier messages into a new file under the
        # new session id; ids billed by any main transcript of this project are skipped.
        seen_file = root / "seen" / (hashlib.sha1(str(path.parent).encode()).hexdigest() + ".txt")
        seen_file.parent.mkdir(exist_ok=True)
        state_file = root / "state" / (hashlib.sha1(str(path).encode()).hexdigest() + ".json")
        seen = set(seen_file.read_text().split()) if not state_file.exists() \
            and seen_file.is_file() else set()
        billed = _bill_file(path, kind, "main", payload, root, prices, now, seen)
        if billed:
            with seen_file.open("a") as fh:
                fh.write("".join(f"{mid}\n" for mid in billed))
        subagents = path.parent / str(payload.get("session_id") or path.stem) / "subagents"
        for agent_file in sorted(subagents.rglob("agent-*.jsonl")) if subagents.is_dir() else []:
            if (root / "state" / (hashlib.sha1(str(agent_file).encode()).hexdigest()
                                  + ".json")).exists():
                _bill_file(agent_file, "subagent", _agent_type(agent_file) or "subagent",
                           payload, root, prices, now)
    return ""


def log(message: str) -> None:
    try:
        root = data_dir()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "hook.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {message}\n")
    except OSError:
        pass


def hook_main(kind: str) -> int:
    """Never fails the session: any error goes to hook.log, exit code is always 0."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if os.environ.get("AGENT_COSTS_DEBUG"):
            log(f"payload {kind} keys={sorted(payload)}")
        message = record(kind, payload)
    except Exception as exc:  # noqa: BLE001 -- bookkeeping must never break a session
        message = f"error {kind} {type(exc).__name__}: {exc}"
    if message:
        log(message)
    return 0


# ---------------------------------------------------------------- report

def load_lines(since: datetime | None) -> list[dict]:
    path = data_dir() / "usage.jsonl"
    out = []
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ts = _ts(row.get("ts"))
        if since and (ts is None or ts < since):
            continue
        out.append(row)
    return out


def group_key(row: dict, by: str) -> str:
    if by in ("day", "week"):
        ts = _ts(row.get("ts"))
        if ts is None:
            return "?"
        local = ts.astimezone()
        if by == "day":
            return local.date().isoformat()
        year, week, _ = local.isocalendar()
        return f"{year}-W{week:02d}"
    value = row.get(by) or "?"
    return value[:8] if by == "session" else value


def _num(n: float) -> str:
    for unit, size in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(n) >= size:
            return f"{n / size:.1f}{unit}"
    return str(int(n))


def report(rows: list[dict], by: str = "agent", top: int = 15, label: str = "") -> str:
    if not rows:
        return "No usage recorded yet."
    groups: dict[str, dict] = defaultdict(lambda: {"runs": 0, "turns": 0, "tok": 0,
                                                   "read": 0, "in": 0, "usd": 0.0,
                                                   "unpriced": 0})
    total, main_usd, unpriced_models = 0.0, 0.0, set()
    for row in rows:
        g = groups[group_key(row, by)]
        g["runs"] += 1
        g["turns"] += row.get("turns") or 0
        g["tok"] += sum(row.get(k) or 0 for k in TOKENS)
        g["read"] += row.get("cache_read") or 0
        g["in"] += sum(row.get(k) or 0 for k in TOKENS if k != "output")
        usd = row.get("usd") or 0.0
        g["usd"] += usd
        total += usd
        if row.get("agent") == "main":
            main_usd += usd
        if row.get("unpriced"):
            g["unpriced"] += 1
            unpriced_models.update(row["unpriced"])
    pct = (lambda x: f"{100 * x / total:.0f}%") if total else (lambda x: "-")
    head = (f"{label}${total:.2f} total · orchestrator (main) ${main_usd:.2f} ({pct(main_usd)})"
            f" · workers ${total - main_usd:.2f} ({pct(total - main_usd)}) · {len(rows)} runs")
    if unpriced_models:
        head += f" · unpriced: {', '.join(sorted(unpriced_models))}"
    order = sorted(groups.items(), key=lambda kv: (kv[0] if by in ("day", "week") else -kv[1]["usd"]))
    if by not in ("day", "week"):
        order = order[:top]
    lines = [head, "",
             f"| {by} | runs | turns | tokens | cache hit | usd | share |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for key, g in order:
        hit = f"{100 * g['read'] / g['in']:.0f}%" if g["in"] else "-"
        usd = f"${g['usd']:.2f}" + (" +unpriced" if g["unpriced"] else "")
        lines.append(f"| {key} | {g['runs']} | {g['turns']} | {_num(g['tok'])} | {hit} "
                     f"| {usd} | {pct(g['usd'])} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("kind", choices=("subagent", "main"))
    rep = sub.add_parser("report")
    rep.add_argument("--by", default="agent",
                     choices=("agent", "project", "session", "model", "day", "week"))
    rep.add_argument("--days", type=float, default=7, help="look back N days (0 = all)")
    rep.add_argument("--project", help="only this project")
    rep.add_argument("--top", type=int, default=15)
    a = ap.parse_args(argv)
    if a.cmd == "record":
        return hook_main(a.kind)
    since = datetime.now(timezone.utc) - timedelta(days=a.days) if a.days else None
    rows = [r for r in load_lines(since) if not a.project or r.get("project") == a.project]
    label = f"Last {a.days:g} days: " if a.days else "All time: "
    print(report(rows, a.by, a.top, label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
