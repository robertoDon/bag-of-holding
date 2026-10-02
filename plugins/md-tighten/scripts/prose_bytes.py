#!/usr/bin/env python3
"""Split Markdown into prose bytes and frozen bytes.

Frozen = front matter, code blocks (fenced or indented) and table rows. An editor
must not touch them, so a cut target measured on total bytes can only be hit by
breaking that rule. Prose is everything else: the only fair denominator.

    prose_bytes.py FILE...                 table of total / frozen / prose bytes
    prose_bytes.py --compare BEFORE AFTER  prose bytes before, after, and the cut %

--compare counts the after's prose as its total minus the before's frozen bytes, so
prose moved into a new table or code block is not a cut.
"""
import re
import sys

FENCE = re.compile(r'^\s*(`{3,}|~{3,})')
DELIM = re.compile(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$')
LIST_ITEM = re.compile(r'^\s*(?:>\s*)*(?:[-*+]|\d+[.)])\s')


def closes(line, fence):
    """True when line closes a block opened with fence (same char, at least as long)."""
    m = FENCE.match(line)
    return bool(m) and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
        and not line.strip().strip(fence[0])


def indent(line):
    return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())


def classify(text):
    """[(line, kind, block)]: kind in prose / front / fence / code / table.

    Lines keep their ends. block numbers each code block (fenced or indented) and is
    None elsewhere.
    """
    lines = text.splitlines(keepends=True)
    kinds = ['prose'] * len(lines)
    block = [None] * len(lines)
    i = 0
    if lines and lines[0].rstrip() == '---':
        for j in range(1, len(lines)):
            if lines[j].rstrip() in ('---', '...'):
                kinds[:j + 1] = ['front'] * (j + 1)
                i = j + 1
                break
    fence, n, in_list = None, 0, False
    while i < len(lines):
        line = lines[i]
        m = FENCE.match(line)
        blank = not line.strip()
        if fence:
            kinds[i], block[i] = 'fence', n
            if closes(line, fence):
                fence = None
        elif m and not (m.group(1)[0] == '`' and '`' in line.strip()[len(m.group(1)):]):
            fence = m.group(1)
            n += 1
            kinds[i], block[i] = 'fence', n
        elif not blank and indent(line) >= 4 and not in_list \
                and (i == 0 or not lines[i - 1].strip() or kinds[i - 1] == 'code'):
            if i == 0 or kinds[i - 1] != 'code':
                n += 1
            kinds[i], block[i] = 'code', n
        elif line.lstrip().startswith('|'):
            kinds[i] = 'table'
        elif '|' in line and i + 1 < len(lines) and '|' in lines[i + 1] \
                and DELIM.match(lines[i + 1]):
            # GFM table without leading pipes: header, delimiter, then rows with a pipe.
            j = i
            while j < len(lines) and lines[j].strip() and '|' in lines[j]:
                kinds[j] = 'table'
                j += 1
            i, in_list = j, False
            continue
        if not blank and kinds[i] == 'prose':
            # Indented text after a list item is the item's continuation, not code.
            in_list = bool(LIST_ITEM.match(line)) or (in_list and indent(line) > 0)
        i += 1
    return list(zip(lines, kinds, block))


def split_bytes(text):
    prose = frozen = 0
    for line, kind, _ in classify(text):
        n = len(line.encode('utf-8'))
        if kind == 'prose':
            prose += n
        else:
            frozen += n
    return prose, frozen


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def main(args):
    if args[:1] == ['--compare'] and len(args) == 3:
        before, frozen = split_bytes(read(args[1]))
        after = len(read(args[2]).encode('utf-8')) - frozen
        cut = round(100 * (before - after) / before, 1) if before else 0.0
        print(f'prose before {before}  after {after}  cut {cut}%')
        return 0
    if not args or args[0].startswith('-'):
        print(__doc__.strip())
        return 2
    width = max(len(p) for p in args) + 2
    print(f"{'file':<{width}}{'total':>8}{'frozen':>8}{'prose':>8}  frozen%")
    for p in args:
        prose, frozen = split_bytes(read(p))
        total = prose + frozen
        pct = round(100 * frozen / total) if total else 0
        print(f'{p:<{width}}{total:>8}{frozen:>8}{prose:>8}  {pct:>6}%')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
