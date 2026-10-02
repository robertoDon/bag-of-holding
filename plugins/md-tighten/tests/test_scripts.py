"""Tests for the meter and the literal check. Run: python3 -m unittest discover tests"""
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
sys.path.insert(0, SCRIPTS)
from check_literals import check as check_full, literals  # noqa: E402
from prose_bytes import classify, read, split_bytes  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def check(befores, afters):
    return check_full(befores, afters)[0]


def kinds(text):
    return [k for _, k, _ in classify(text)]


class ProseBytes(unittest.TestCase):
    def test_table_rows_are_frozen(self):
        text = 'Intro\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n'
        self.assertEqual(kinds(text), ['prose', 'prose', 'table', 'table', 'table'])

    def test_table_without_leading_pipes(self):
        text = 'a | b\n--- | ---\n1 | 2\n\nafter | not a table\n'
        self.assertEqual(kinds(text), ['table', 'table', 'table', 'prose', 'prose'])

    def test_pipe_in_prose_is_prose(self):
        self.assertEqual(kinds('use a | b in a shell\nnext line\n'), ['prose', 'prose'])

    def test_code_block_is_frozen_including_tables_inside(self):
        text = '```md\n| x |\n# not a heading\n```\nprose\n'
        self.assertEqual(kinds(text), ['fence'] * 4 + ['prose'])

    def test_tilde_fence_ignores_backtick_fence_inside(self):
        text = '~~~\n```\nstill code\n~~~\nprose\n'
        self.assertEqual(kinds(text), ['fence'] * 4 + ['prose'])

    def test_longer_fence_needs_as_long_a_close(self):
        text = '````\n```\ncode\n````\nprose\n'
        self.assertEqual(kinds(text), ['fence'] * 4 + ['prose'])

    def test_unclosed_fence_runs_to_end(self):
        self.assertEqual(kinds('prose\n```\ncode\n'), ['prose', 'fence', 'fence'])

    def test_inline_triple_backticks_are_not_a_fence(self):
        self.assertEqual(kinds('```inline``` here\nprose\n'), ['prose', 'prose'])

    def test_fence_inside_nested_list(self):
        text = '- item\n  - nested\n    ```sh\n    ls\n    ```\n  - back\n'
        self.assertEqual(kinds(text), ['prose', 'prose', 'fence', 'fence', 'fence', 'prose'])

    def test_indented_code_block_is_frozen(self):
        text = 'Run:\n\n    make all\n    make test\n\nprose\n'
        self.assertEqual(kinds(text), ['prose', 'prose', 'code', 'code', 'prose', 'prose'])

    def test_indented_list_continuation_is_prose(self):
        text = '- item\n\n    more of the item\n'
        self.assertEqual(kinds(text), ['prose'] * 3)

    def test_front_matter_is_frozen(self):
        text = '---\ntitle: x\n---\nbody\n'
        self.assertEqual(kinds(text), ['front', 'front', 'front', 'prose'])

    def test_rule_without_closing_is_not_front_matter(self):
        self.assertEqual(kinds('---\nbody\n'), ['prose', 'prose'])

    def test_horizontal_rule_later_is_prose(self):
        self.assertEqual(kinds('body\n---\nmore\n'), ['prose'] * 3)

    def test_bytes_are_utf8(self):
        prose, frozen = split_bytes('ação\n| é |\n')
        self.assertEqual((prose, frozen), (7, 7))

    def test_compare_cli(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, 'a.md'), os.path.join(d, 'b.md')
            write(a, 'x' * 99 + '\n')
            write(b, 'x' * 74 + '\n')
            out = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'prose_bytes.py'),
                                  '--compare', a, b], capture_output=True, text=True).stdout
            self.assertIn('cut 25.0%', out)


    def test_compare_does_not_count_prose_moved_into_a_table(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, 'a.md'), os.path.join(d, 'b.md')
            write(a, 'The port is 80 and the host is db.\n')
            write(b, '| port | 80 |\n| --- | --- |\n| host | db |\n')
            out = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'prose_bytes.py'),
                                  '--compare', a, b], capture_output=True, text=True).stdout
            self.assertNotIn('cut 100', out)


class Literals(unittest.TestCase):
    def lits(self, text):
        return set(literals(text))

    def test_kinds_of_literals(self):
        text = ('Run `make test` with --verbose or -v. See https://example.com/a?b=1 and '
                'docs/guide/setup.md, config.yaml, ~/.config/x. Timeout 30 s, 25%, $0.08, '
                'v2.1, 2026-09-30 at 08:30. Ask ops@example.com. Set $HOME. Uses AWS S3 and '
                'GitHub. Field needs_review. Page [[Home]]. Ping #ops-oncall, see s3://bucket/key.\n')
        self.assertTrue({'make test', '--verbose', '-v', 'https://example.com/a?b=1',
                         'docs/guide/setup.md', 'config.yaml', '~/.config/x', '30 s', '25%',
                         '$0.08', 'v2.1', '2026-09-30', '08:30', 'ops@example.com', '$HOME',
                         'AWS', 'S3', 'GitHub', 'needs_review', '[[Home]]', '#ops-oncall',
                         's3://bucket/key'} <= self.lits(text))

    def test_prose_noise_is_not_a_literal(self):
        lits = self.lits('NOTE: this is IMPORTANT, e.g. and/or i.e. the 3rd well-known one.\n')
        self.assertEqual(lits, set())

    def test_caps_contractions_are_emphasis(self):
        self.assertEqual(self.lits("DON'T push. WON'T fix.\n"), set())

    def test_slashed_words_are_prose(self):
        self.assertEqual(self.lits('grants read/write/execute, works w/ Bash\n'), set())

    def test_indented_code_is_not_scanned(self):
        self.assertEqual(self.lits('Run:\n\n    rm -rf /tmp/x --force 42\n'), set())

    def test_list_markers_are_not_numbers(self):
        self.assertEqual(self.lits('1. first\n2) second\n  - nested\n    10. deep\n'), set())

    def test_link_target_kept_text_free(self):
        self.assertEqual(self.lits('Read [the guide](guide/intro.md).\n'), {'guide/intro.md'})

    def test_code_block_contents_are_not_prose_literals(self):
        self.assertEqual(self.lits('```\nrm -rf /tmp/x 42\n```\n'), set())

    def test_front_matter_is_not_scanned(self):
        self.assertEqual(self.lits('---\nversion: 3\n---\nhi\n'), set())

    def test_table_cells_are_scanned(self):
        self.assertIn('512 MB', self.lits('| mem | 512 MB |\n| --- | --- |\n'))

    def test_line_numbers_survive_frozen_lines(self):
        text = '---\na: 1\n---\n```\nx\n```\nport 8080\n'
        self.assertEqual(literals(text), {'8080': 7})


class Check(unittest.TestCase):
    def test_identity_passes_on_every_fixture(self):
        for name in os.listdir(FIXTURES):
            if name.endswith('.md'):
                text = read(os.path.join(FIXTURES, name))
                self.assertEqual(check([text], [text]), [], name)

    def test_dropped_literal_fails_and_is_named(self):
        problems = check(['Retry 3 times, wait 30 s, then call `notify()`.\n'],
                         ['Retry, then call `notify()`.\n'])
        self.assertEqual(problems, ['missing literal (line 1): 3',
                                    'missing literal (line 1): 30 s'])

    def test_unit_synonym_and_reflow_pass(self):
        before = 'The job waits 30 seconds\nbefore it calls `notify()` again.\n'
        after = '- Waits 30 s.\n- Then calls notify() again.\n'
        self.assertEqual(check([before], [after]), [])

    def test_part_of_a_bigger_token_is_not_a_literal(self):
        self.assertEqual(check(['Wi-Fi 802.11ax, firmware V2.0.\n'], ['Wi-Fi 6, firmware 2.\n']), [])

    def test_unit_spacing_is_free(self):
        self.assertEqual(check(['Max 512 MB.\n'], ['Max 512MB.\n']), [])

    def test_deleting_a_repeated_code_block_fails(self):
        block = '```sh\nmake deploy\n```\n'
        self.assertEqual(check(['Staging:\n' + block + 'Prod:\n' + block], ['Both:\n' + block]),
                         ['code block changed or gone (1x): make deploy'])

    def test_indented_code_changed_fails_and_fenced_rewrite_passes(self):
        before = 'Run:\n\n    rm -rf /tmp/x\n'
        self.assertEqual(check([before], ['Run:\n\n```\nrm -rf /tmp/x\n```\n']), [])
        self.assertEqual(check([before], ['Run:\n\n    rm -r /tmp/x\n'])[0],
                         'code block changed or gone (1x): rm -rf /tmp/x')

    def test_number_inside_bigger_number_does_not_count(self):
        self.assertEqual(check(['use 8 workers\n'], ['use 18 workers or 8.5\n']),
                         ['missing literal (line 1): 8'])

    def test_changed_code_block_fails(self):
        before = 'Run:\n\n```sh\nmake all\n```\n'
        self.assertEqual(check([before], ['Run:\n\n```sh\nmake al\n```\n']),
                         ['code block changed or gone (1x): make all'])

    def test_code_block_reindented_in_list_passes(self):
        before = 'Run:\n\n```sh\nmake all\n```\n'
        after = '- Run:\n\n  ```sh\n  make all\n  ```\n'
        self.assertEqual(check([before], [after]), [])

    def test_flattened_table_fails(self):
        before = '| k | v |\n| --- | --- |\n| port | 80 |\n| host | db |\n'
        after = '| k | v |\n| --- | --- |\n| port | 80 |\n- host: db\n'
        self.assertEqual(check([before], [after]), ['table rows dropped: 3 -> 2'])

    def test_front_matter_change_fails(self):
        self.assertEqual(check(['---\na: 1\n---\nx\n'], ['---\na: 2\n---\nx\n']),
                         ['front matter changed (line 1)'])

    def test_owners_mode_checks_the_union(self):
        befores = ['Port 8080. Owner team-db.\n', 'Deploy on Friday.\n']
        afters = ['Port 8080.\n', 'Deploy on Friday. Owner team-db.\n']
        self.assertEqual(check(befores, afters), [])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, 'a.md'), os.path.join(d, 'b.md')
            write(a, 'Keep `--force` off.\n')
            write(b, 'Keep it off.\n')
            run = lambda *x: subprocess.run([sys.executable, os.path.join(SCRIPTS, 'check_literals.py'), *x],
                                            capture_output=True, text=True)
            fail = run(a, b)
            self.assertEqual(fail.returncode, 1)
            self.assertIn('missing literal (line 1): --force', fail.stdout)
            self.assertEqual(run(a, a).returncode, 0)
            self.assertEqual(run('--before', a, '--after', a).returncode, 0)
            self.assertEqual(run(a).returncode, 2)


if __name__ == '__main__':
    unittest.main()
