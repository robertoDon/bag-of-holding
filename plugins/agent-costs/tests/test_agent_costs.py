"""Hand-built transcripts through the hook and the report. Run: python3 -m unittest discover tests"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agent_costs as ac  # noqa: E402


def assistant(mid, model="claude-sonnet-5-5", usage=None, blocks=None, ts="2026-10-01T10:00:00Z",
              sidechain=False):
    return {"type": "assistant", "timestamp": ts, "isSidechain": sidechain,
            "message": {"id": mid, "role": "assistant", "model": model,
                        "usage": usage or {}, "content": blocks or [{"type": "text", "text": "x"}]}}


def user(ts="2026-10-01T10:00:00Z", text="hi"):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def tool(tid):
    return [{"type": "tool_use", "id": tid, "name": "Read", "input": {"file_path": "/secret"}}]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["AGENT_COSTS_DIR"] = str(self.tmp / "data")
        self.proj = self.tmp / "transcripts"
        (self.proj / "sess1" / "subagents").mkdir(parents=True)
        self.main = self.proj / "sess1.jsonl"

    def write(self, path, rows, mode="w", trailing_newline=True):
        text = "".join(json.dumps(r) + "\n" for r in rows)
        if not trailing_newline:
            text = text[:-1]
        with path.open(mode) as fh:
            fh.write(text)

    def lines(self):
        path = self.tmp / "data" / "usage.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def sub(self, agent_id, rows, agent_type="Explore"):
        path = self.proj / "sess1" / "subagents" / f"agent-{agent_id}.jsonl"
        self.write(path, rows)
        path.with_name(f"agent-{agent_id}.meta.json").write_text(json.dumps({"agentType": agent_type}))
        return ac.record("subagent", {"session_id": "sess1", "transcript_path": str(self.main),
                                      "agent_id": agent_id, "cwd": str(self.tmp)})

    def main_turn(self):
        return ac.record("main", {"session_id": "sess1", "transcript_path": str(self.main),
                                  "cwd": str(self.tmp)})


class TestRecord(Base):
    def test_simple_subagent(self):
        self.sub("a1", [user(), assistant("m1", usage={"input_tokens": 1000, "output_tokens": 10},
                                          blocks=tool("t1")),
                        assistant("m1", usage={"input_tokens": 1000, "output_tokens": 200},
                                  ts="2026-10-01T10:00:05Z")])
        [line] = self.lines()
        self.assertEqual(line["agent"], "Explore")
        self.assertEqual((line["input"], line["output"], line["turns"], line["tool_calls"]),
                         (1000, 200, 1, 1))            # per-field max, not per-line sum
        self.assertAlmostEqual(line["usd"], (1000 * 2 + 200 * 10) / 1e6)
        self.assertEqual(line["duration_ms"], 5000)
        self.assertNotIn("/secret", json.dumps(line))   # no content leaks

    def test_subagent_with_cache(self):
        u = {"input_tokens": 5, "output_tokens": 100, "cache_read_input_tokens": 50_000,
             "cache_creation_input_tokens": 3000,
             "cache_creation": {"ephemeral_5m_input_tokens": 2000, "ephemeral_1h_input_tokens": 1000}}
        self.sub("a2", [assistant("m1", model="claude-opus-5-5", usage=u)])
        [line] = self.lines()
        self.assertEqual((line["cache_read"], line["cache_write_5m"], line["cache_write_1h"]),
                         (50_000, 2000, 1000))
        expected = (5 * 4 + 100 * 20 + 50_000 * 0.20 + 2000 * 5 + 1000 * 8) / 1e6
        self.assertAlmostEqual(line["usd"], expected)

    def test_main_session_bills_only_the_delta(self):
        self.write(self.main, [user(), assistant("m1", usage={"input_tokens": 100, "output_tokens": 50})])
        self.main_turn()
        # A sidechain line in the main file belongs to the subagent hook.
        self.write(self.main, [user("2026-10-01T10:01:00Z"),
                               assistant("s1", usage={"input_tokens": 9999}, sidechain=True),
                               assistant("m2", usage={"input_tokens": 300, "output_tokens": 70},
                                         ts="2026-10-01T10:01:09Z")], mode="a")
        self.main_turn()
        self.main_turn()                                  # nothing new: no third line
        first, second = self.lines()
        self.assertEqual((first["input"], second["input"], second["output"]), (100, 300, 70))
        self.assertEqual((first["agent"], second["turns"], second["duration_ms"]), ("main", 1, 9000))

    def test_message_split_across_two_records(self):
        self.write(self.main, [assistant("m1", usage={"input_tokens": 100, "output_tokens": 5})])
        self.main_turn()
        self.write(self.main, [assistant("m1", usage={"input_tokens": 100, "output_tokens": 80})], mode="a")
        self.main_turn()
        first, second = self.lines()
        self.assertEqual((second["input"], second["output"], second["turns"]), (0, 75, 0))
        self.assertEqual(first["output"] + second["output"], 80)

    def test_resumed_subagent_bills_only_new_messages(self):
        rows = [assistant("m1", usage={"input_tokens": 10, "output_tokens": 1})]
        self.sub("a3", rows)
        self.sub("a3", rows + [assistant("m2", usage={"input_tokens": 20, "output_tokens": 2})])
        self.assertEqual([l["input"] for l in self.lines()], [10, 20])

    def test_unpriced_model(self):
        self.sub("a4", [assistant("m1", model="claude-future-9", usage={"input_tokens": 10})])
        [line] = self.lines()
        self.assertIsNone(line["usd"])
        self.assertEqual(line["unpriced"], ["claude-future-9"])
        out = ac.report(self.lines())
        self.assertIn("unpriced: claude-future-9", out)
        self.assertIn("+unpriced", out)

    def test_snapshot_date_and_synthetic(self):
        self.sub("a5", [assistant("m1", model="claude-haiku-4-5-20251001", usage={"input_tokens": 1_000_000}),
                        assistant("m2", model="<synthetic>", usage={"input_tokens": 0})])
        [line] = self.lines()
        self.assertAlmostEqual(line["usd"], 1.0)
        self.assertNotIn("unpriced", line)
        self.assertEqual(line["turns"], 1)            # the zero-usage stub is not a call

    def test_truncated_transcript(self):
        good = assistant("m1", usage={"input_tokens": 100, "output_tokens": 1})
        self.write(self.main, [good])
        with self.main.open("a") as fh:
            fh.write('{"type": "assistant", "message": {"id": "m2", "usa')   # cut mid-line
        self.main_turn()
        [line] = self.lines()
        self.assertEqual(line["input"], 100)
        with self.main.open("a") as fh:                   # the line completes later
            fh.write('ge": {"input_tokens": 7}, "role": "assistant", "model": "claude-sonnet-5-5"}}\n')
        self.main_turn()
        self.assertEqual(self.lines()[1]["input"], 7)

    def test_fast_mode_and_user_price_override(self):
        (self.tmp / "data").mkdir()
        (self.tmp / "data" / "prices.json").write_text(json.dumps(
            {"models": {"claude-future-9": {"input": 1, "output": 1, "cache_read": 0,
                                            "cache_write_5m": 0, "cache_write_1h": 0}}}))
        self.sub("a6", [assistant("m1", model="claude-opus-5-5",
                                  usage={"input_tokens": 1_000_000, "speed": "fast"}),
                        assistant("m2", model="claude-future-9", usage={"input_tokens": 1_000_000})])
        [line] = self.lines()
        self.assertAlmostEqual(line["usd"], 8.0 + 1.0)
        self.assertEqual(line["models"], ["claude-future-9", "claude-opus-5-5"])

    def test_forked_session_skips_copied_history(self):
        self.write(self.main, [assistant("m1", usage={"input_tokens": 100})])
        self.main_turn()
        fork = self.proj / "sess2.jsonl"
        self.write(fork, [assistant("m1", usage={"input_tokens": 100}),
                          assistant("m9", usage={"input_tokens": 5})])
        ac.record("main", {"session_id": "sess2", "transcript_path": str(fork), "cwd": str(self.tmp)})
        self.assertEqual([l["input"] for l in self.lines()], [100, 5])

    def test_main_stop_catches_up_a_subagent_flushed_late(self):
        path = self.proj / "sess1" / "subagents" / "agent-a7.jsonl"
        self.sub("a7", [assistant("m1", usage={"input_tokens": 10, "output_tokens": 3})])
        self.write(path, [assistant("m1", usage={"input_tokens": 10, "output_tokens": 90})], mode="a")
        self.write(self.main, [assistant("x1", usage={"input_tokens": 1})])
        self.main_turn()
        sub1, main, sub2 = self.lines()
        self.assertEqual((sub2["agent"], sub2["agent_id"], sub2["output"], sub2["turns"]),
                         ("Explore", "a7", 87, 0))

    def test_partial_or_broken_price_override(self):
        (self.tmp / "data").mkdir()
        prices = self.tmp / "data" / "prices.json"
        prices.write_text(json.dumps({"models": {"claude-sonnet-5-5": {"input": 3},
                                                 "claude-half": {"input": 1}}}))
        self.sub("a8", [assistant("m1", usage={"input_tokens": 1_000_000}),
                        assistant("m2", model="claude-half", usage={"input_tokens": 1})])
        [line] = self.lines()
        self.assertAlmostEqual(line["usd"], 3.0)       # field merged, other rates kept
        self.assertEqual(line["unpriced"], ["claude-half"])   # incomplete rate is no rate
        prices.write_text("{not json")
        self.assertIn("claude-opus-5-5", ac.load_prices())

    def test_hook_never_fails(self):
        sys.stdin = io.StringIO("not json")
        try:
            self.assertEqual(ac.hook_main("main"), 0)
        finally:
            sys.stdin = sys.__stdin__
        self.assertIn("error main", (self.tmp / "data" / "hook.log").read_text())


class TestReport(Base):
    def test_table(self):
        self.write(self.main, [assistant("m1", usage={"input_tokens": 1_000_000})])
        self.main_turn()
        self.sub("a1", [assistant("m1", usage={"input_tokens": 500_000})])
        buf = io.StringIO()
        with redirect_stdout(buf):
            ac.main(["report", "--days", "0"])
        out = buf.getvalue()
        self.assertIn("$3.00 total", out)
        self.assertIn("orchestrator (main) $2.00 (67%)", out)
        self.assertIn("| main | 1 | 1 |", out)
        for by in ("project", "session", "model", "day", "week"):
            self.assertIn(f"| {by} |", ac.report(self.lines(), by))


if __name__ == "__main__":
    unittest.main()
