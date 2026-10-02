#!/usr/bin/env python3
"""Score a real run on the fixtures: prose cut and planted facts kept.

    eval_planted.py BEFORE_DIR AFTER_DIR

A planted fact survives when all its anchor regexes match (case-insensitive) inside a
window of 3 consecutive lines of the after. The literal check and the fact-checker are
the plugin's own gates; this is the test's independent count.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
from prose_bytes import read, split_bytes  # noqa: E402


def survives(anchors, lines, window=3):
    for i in range(len(lines)):
        chunk = ' '.join(lines[i:i + window])
        if all(re.search(a, chunk, re.I) for a in anchors):
            return True
    return False


def main(before_dir, after_dir):
    facts = json.load(open(os.path.join(HERE, 'fixtures', 'planted-facts.json')))
    cuts, kept_all, total_all = [], 0, 0
    for name, planted in facts.items():
        before = split_bytes(read(os.path.join(before_dir, name)))[0]
        after_text = read(os.path.join(after_dir, name))
        after = split_bytes(after_text)[0]
        lines = after_text.splitlines()
        lost = [f for f, anchors in planted if not survives(anchors, lines)]
        cut = 100 * (before - after) / before
        cuts.append(cut)
        kept_all += len(planted) - len(lost)
        total_all += len(planted)
        print(f'{name:<22} prose {before:>5} -> {after:>5}  cut {cut:5.1f}%  facts {len(planted) - len(lost)}/{len(planted)}')
        for f in lost:
            print(f'    LOST: {f}')
    print(f'{"mean":<22} {"":>20} cut {sum(cuts) / len(cuts):5.1f}%  facts {kept_all}/{total_all}')
    return 0 if kept_all == total_all else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]) if len(sys.argv) == 3 else 2)
