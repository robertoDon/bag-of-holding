#!/usr/bin/env python3
"""Fail when a rewrite of Markdown dropped a literal.

    check_literals.py BEFORE AFTER
    check_literals.py --before A.md B.md --after A.md B.md   (owners mode: unions)

Literals: inline code, URLs, link targets, paths and file names, flags, emails, #channels,
env vars, dates and times, numbers (with their unit), ALL-CAPS and CamelCase names,
snake_case identifiers. Every literal of the before must appear in the after as a
whole token. Code blocks (by content) and front matter must survive verbatim, and the
after may not have fewer table rows. Exit 0 pass, 1 fail (with the list), 2 usage.
"""
import os
import re
import sys
import textwrap
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prose_bytes import DELIM, FENCE, classify, read  # noqa: E402

# Caps words that are emphasis, not names. A missing NEVER is the fact-checker's job.
EMPHASIS = set("""
A I OK NOTE NOTES IMPORTANT WARNING CAUTION TIP TIPS NB PS FYI TL DR TLDR ALWAYS NEVER MUST
NOT DO DONT WONT CANT ISNT SHOULD ONLY ALL NO YES AND OR THE IF ANY EVERY NOW STOP THIS THAT THESE FIRST
LAST EXACTLY NONE BEFORE AFTER NEXT ONE BOTH EITHER WITHOUT WITH FOR ALSO CANNOT CAN WILL
IS ARE BE IN ON AT TO OF BY EVEN VERY SAME NOTHING EVERYTHING REQUIRED OPTIONAL CRITICAL
NEW DONE
NOTA OBS DICA AVISO SEMPRE NUNCA SO NAO E OU ESTE ESSE ISSO PRIMEIRO NADA TUDO ANTES DEPOIS
COM SEM PARA MAS TAMBEM OBRIGATORIO
""".split())
ABBREV = {'e.g', 'i.e', 'a.k.a', 'p.ex', 'p.ej', 'z.B', 'd.h', 'et.al'}

# A unit may be rewritten as any synonym in its family: "30 seconds" -> "30 s" keeps the fact.
UNIT_FAMILIES = [
    ['%', 'percent', 'por cento'],
    ['s', 'sec', 'secs', 'second', 'seconds', 'segundo', 'segundos'],
    ['min', 'mins', 'minute', 'minutes', 'minuto', 'minutos'],
    ['h', 'hr', 'hrs', 'hour', 'hours', 'hora', 'horas'],
    ['d', 'day', 'days', 'dia', 'dias'],
    ['wk', 'week', 'weeks', 'semana', 'semanas'],
    ['mo', 'month', 'months', 'mês', 'mes', 'meses'],
    ['y', 'yr', 'yrs', 'year', 'years', 'ano', 'anos'],
    ['lb', 'lbs'],
]
UNIT_ATTACHED = r'%|ms|s|sec|min|h|d|wk|mo|yr|y|[kKMGT]i?B|B|px|em|rem|pt|in|cm|mm|m|km|kg|g|lbs?|oz|[kMG]?Hz|[km]?W|V|mAh|mA|A|x|k|K|M|bn|°[CF]'
UNIT_SPACED = r'%|ms|s|h|secs?|seconds?|mins?|minutes?|hours?|hrs?|days?|weeks?|months?|years?|[kKMGT]i?B|px|rem|pt|cm|mm|km|kg|lbs?|oz|[kMG]?Hz|kW|mAh|mA|°[CF]|USD|EUR|BRL|percent|por cento|tokens?|bytes?|chars?|words?|lines?|segundos?|minutos?|horas?|dias?|semanas?|mês|meses|anos?|palavras?|linhas?'
SEG = r'[\w.<>*{}$@+-]'

PATTERNS = [
    ('url', r'\b[a-z][a-z0-9+.-]*://[^\s<>()\[\]`"\']+[^\s<>()\[\]`"\'.,;:!?]'),
    ('email', r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b'),
    ('date', r'\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?\b'
             r'|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b'),
    ('env', r'\$\{?[A-Za-z_]\w*\}?'),
    ('path', rf'(?:~|\.{{1,2}})/{SEG}+(?:/{SEG}+)*/?'                    # ~/x ./x ../x
             rf'|(?<![\w/]){SEG}*/{SEG}+(?:/{SEG}+)+/?'                  # a/b/c, /usr/bin
             rf'|(?<![\w/.-]){SEG}+/(?:{SEG}+\.[A-Za-z]\w{{0,5}}\b|(?=[\s,;:)]|$))'),  # a/b.md, src/
    ('file', r'(?<![\w/.-])[\w-]+(?:\.[\w-]+)*\.[A-Za-z][A-Za-z0-9]{1,5}\b(?!\.\w)'),
    ('flag', r'(?<![\w-])--[A-Za-z][\w-]*|(?<![\w-])-[A-Za-z]{1,3}\b(?!-)'),
    ('wiki', r'\[\[[^\]]+\]\]'),
    ('channel', r'(?<![\w&#/])#[A-Za-z0-9][\w-]*[A-Za-z0-9]'),
    ('version', r'\bv\d+(?:\.\d+)*\b'),
    ('money', r'(?:R\$|US\$|[$€£¥])\s?\d+(?:[.,]\d+)*'),
    ('number', r'(?<![\w.])\d+(?:[.,]\d+)*(?:(?:' + UNIT_ATTACHED + r')(?![\w])|\s(?:'
               + UNIT_SPACED + r')(?![\w])|(?![\w]))'),
    ('snake', r'\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b'),
    ('caps', r"\b[A-Z][A-Z0-9]+(?:[-_'’][A-Z0-9]+)*\b"),
    ('camel', r'\b[A-Za-z]*[a-z][A-Z][A-Za-z0-9]*\b|\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b'),
]
TOKEN = re.compile('|'.join(f'(?P<{k}>{p})' for k, p in PATTERNS))
CODE_SPAN = re.compile(r'(`+)(.+?)\1')
LINK = re.compile(r'\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)|^\s*\[[^\]]+\]:\s*(\S+)', re.M)
LIST_MARKER = re.compile(r'^(\s*(?:>\s*)*)(?:\d+[.)]|[-*+])(?=\s)')
NUM_UNIT = re.compile(r'^(\d+(?:[.,]\d+)*)\s?(\D.*)$')


def parts(text):
    """(front matter, [code block contents, dedented], table row count, body).

    A code block is compared by its content: fence lines and indentation don't count.
    Body is the prose and table text with list markers removed and every frozen line
    blanked, so offsets in it map to the original line numbers.
    """
    front, blocks, rows, body = [], {}, 0, []
    for line, kind, block in classify(text):
        end = '\n' if line.endswith('\n') else ''
        if kind == 'front':
            front.append(line)
            body.append(end)
        elif block is not None:
            if kind == 'code' or not FENCE.match(line):
                blocks.setdefault(block, []).append(line)
            else:
                blocks.setdefault(block, [])
            body.append(end)
        else:
            if kind == 'table' and not DELIM.match(line):
                rows += 1
            body.append(LIST_MARKER.sub(r'\1', line))
    code = [textwrap.dedent(''.join(b)).strip('\n') for b in blocks.values()]
    return ''.join(front), code, rows, ''.join(body)


def literals(text):
    """{literal: first line number} for the prose and tables of one document."""
    found = {}
    body = parts(text)[3]

    def add(lit, pos):
        lit = ' '.join(lit.split())
        if lit and lit not in found:
            found[lit] = body.count('\n', 0, pos) + 1

    for m in CODE_SPAN.finditer(body):
        add(m.group(2), m.start())
    masked = CODE_SPAN.sub(lambda m: ' ' * len(m.group(0)), body)
    for m in LINK.finditer(masked):
        add(m.group(1) or m.group(2), m.start())
    masked = LINK.sub(lambda m: ' ' * len(m.group(0)), masked)
    for m in TOKEN.finditer(masked):
        kind, lit = m.lastgroup, m.group(0)
        if kind == 'caps' and re.sub(r"['’]", '', lit) in EMPHASIS:
            continue
        if kind == 'file' and lit in ABBREV:
            continue
        if kind == 'path':
            lit = lit.rstrip('.')  # sentence end, not part of the path
            # Bare word/word/word is prose ("read/write"); a path has a mark of one.
            if not re.match(r'[~./]', lit) and not re.search(r'[._<>{}*$@0-9]', lit) \
                    and not (lit.endswith('/') and len(lit) > 3):
                continue
        # Part of a bigger token ("802" in "802.11ax"): not a literal on its own.
        if token_re(lit).match(body, m.start()):
            add(lit, m.start())
    return found


def token_re(lit):
    """Regex for lit as a whole token. Whitespace-insensitive.

    A number keeps its unit, with or without a space; a unit in UNIT_FAMILIES may
    become any synonym ("30 seconds" -> "30 s").
    """
    m = NUM_UNIT.match(lit)
    if m:
        family = next((f for f in UNIT_FAMILIES if m.group(2) in f), [m.group(2)])
        pat = re.escape(m.group(1)) + r'\s?(?:' + '|'.join(
            r'\s+'.join(map(re.escape, u.split())) for u in family) + ')'
    else:
        pat = r'\s+'.join(re.escape(w) for w in lit.split())
    lead = r'(?<![\w])(?<!\d[.,])' if re.match(r'\w', lit) else ''
    tail = r'(?![\w])(?![.,]\d)' if re.search(r'\w$', lit) else ''
    return re.compile(lead + pat + tail)


def present(lit, haystack):
    return token_re(lit).search(haystack) is not None


def check(befores, afters):
    """(problems as human-readable lines, number of literals checked). No problems = pass."""
    after_parts = [parts(t) for t in afters]
    after_text = '\n'.join(afters)
    after_blocks = Counter(b for p in after_parts for b in p[1])
    after_fronts = {p[0] for p in after_parts}
    after_rows = sum(p[2] for p in after_parts)
    problems, rows, seen = [], 0, set()
    before_blocks = Counter()
    for i, text in enumerate(befores, 1):
        front, blocks, n_rows, _ = parts(text)
        rows += n_rows
        before_blocks.update(blocks)
        doc = f'doc {i}, ' if len(befores) > 1 else ''
        if front and front not in after_fronts:
            problems.append(f'front matter changed ({doc}line 1)')
        for lit, line in literals(text).items():
            seen.add(lit)
            if not present(lit, after_text):
                problems.append(f'missing literal ({doc}line {line}): {lit}')
    for b, n in (before_blocks - after_blocks).items():
        first = next((ln for ln in b.splitlines() if ln.strip()), '')
        problems.append(f'code block changed or gone ({n}x): {first.strip()[:60]}')
    if after_rows < rows:
        problems.append(f'table rows dropped: {rows} -> {after_rows}')
    return problems, len(seen)


def main(args):
    if len(args) == 2 and not args[0].startswith('-'):
        befores, afters = args[:1], args[1:]
    elif args[:1] == ['--before'] and '--after' in args:
        k = args.index('--after')
        befores, afters = args[1:k], args[k + 1:]
    else:
        befores = afters = []
    if not befores or not afters:
        print(__doc__.strip())
        return 2
    problems, total = check([read(p) for p in befores], [read(p) for p in afters])
    if problems:
        print(f'FAIL: {len(problems)} problem(s) across {total} literal(s)')
        for p in problems:
            print(f'  - {p}')
        return 1
    print(f'PASS: {total} literal(s) kept; code blocks, front matter and table rows intact')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
