#!/usr/bin/env python3
"""Tests for html_lang_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import html_lang_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


class TestValidLang(unittest.TestCase):
    def test_plain_two_letter_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="en">'), [])

    def test_german_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="de">'), [])

    def test_language_region_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="en-US">'), [])

    def test_language_script_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="zh-Hans">'), [])

    def test_language_script_region_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="zh-Hans-CN">'), [])

    def test_three_letter_language_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="fil">'), [])

    def test_numeric_region_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="es-419">'), [])

    def test_script_only_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="sr-Latn">'), [])

    def test_variant_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="de-1996">'), [])

    def test_region_lowercase_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="pt-br">'), [])

    def test_uppercase_language_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="EN">'), [])

    def test_single_quoted_value_passes(self):
        self.assertEqual(checker.find_lang_problems(
            "<html lang='en'>"), [])

    def test_unquoted_value_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang=en>'), [])

    def test_value_with_surrounding_spaces_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang=" en ">'), [])

    def test_self_closing_html_tag_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<html lang="en" />'), [])


class TestFindLangProblems(unittest.TestCase):
    def test_missing_lang_fails_with_file_line(self):
        got = checker.find_lang_problems('<html>\n<head></head>')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 1)
        self.assertIsNone(got[0]["lang"])
        self.assertEqual(got[0]["reason"], "missing lang attribute")

    def test_missing_lang_line_number(self):
        html = ('<!DOCTYPE html>\n<html>\n<head>\n'
                '<title>T</title>\n</head>')
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 2)

    def test_empty_lang_fails(self):
        got = checker.find_lang_problems('<html lang="">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "empty lang attribute")

    def test_whitespace_only_lang_fails_as_empty(self):
        got = checker.find_lang_problems('<html lang="   ">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "empty lang attribute")

    def test_malformed_word_fails(self):
        got = checker.find_lang_problems('<html lang="english">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")
        self.assertEqual(got[0]["lang"], "english")

    def test_malformed_one_letter_fails(self):
        got = checker.find_lang_problems('<html lang="e">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_malformed_underscore_fails(self):
        got = checker.find_lang_problems('<html lang="en_US">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_malformed_trailing_dash_fails(self):
        got = checker.find_lang_problems('<html lang="en-">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_malformed_digits_only_fails(self):
        got = checker.find_lang_problems('<html lang="123">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_malformed_double_dash_fails(self):
        got = checker.find_lang_problems('<html lang="en--US">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_malformed_four_letter_language_fails(self):
        got = checker.find_lang_problems('<html lang="engl">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_lang_on_body_only_fails(self):
        html = '<html><body lang="en"></body></html>'
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "missing lang attribute")

    def test_lang_on_div_only_fails(self):
        html = '<html><div lang="en">text</div></html>'
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "missing lang attribute")

    def test_uppercase_html_and_lang_passes(self):
        self.assertEqual(checker.find_lang_problems(
            '<HTML LANG="en-GB">'), [])

    def test_uppercase_malformed_found(self):
        got = checker.find_lang_problems('<HTML LANG="ENGLISH">')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "malformed lang value")

    def test_multiple_html_first_good_second_bad(self):
        html = '<html lang="en">\n<html>'
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 2)
        self.assertEqual(got[0]["reason"], "missing lang attribute")

    def test_multiple_html_both_bad(self):
        html = '<html>\n<html lang="english">'
        got = checker.find_lang_problems(html)
        self.assertEqual(
            [(g["line"], g["reason"]) for g in got],
            [(1, "missing lang attribute"),
             (2, "malformed lang value")])

    def test_problems_in_document_order_with_lines(self):
        html = ('<html>\n<p>text</p>\n<html lang="english">\n'
                '<html lang="de">\n<html lang="">')
        got = checker.find_lang_problems(html)
        self.assertEqual(
            [(g["line"], g["reason"]) for g in got],
            [(1, "missing lang attribute"),
             (3, "malformed lang value"),
             (5, "empty lang attribute")])

    def test_no_html_element_at_all(self):
        got = checker.find_lang_problems(
            '<head><title>T</title></head><body><p>x</p></body>')
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0]["line"])
        self.assertEqual(got[0]["reason"], "no <html> element found")

    def test_empty_file_reports_no_html(self):
        got = checker.find_lang_problems("")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "no <html> element found")

    def test_whitespace_only_file_reports_no_html(self):
        got = checker.find_lang_problems("  \n\n  ")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "no <html> element found")

    def test_malformed_html_tolerated(self):
        html = '<html lang="en">\n<p>unclosed text'
        self.assertEqual(checker.find_lang_problems(html), [])

    def test_unclosed_html_tag_found(self):
        html = '<html>\n<p>unclosed text'
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 1)

    def test_html_inside_comment_ignored(self):
        html = ('<!-- <html lang="en"> not a real element -->\n'
                '<body><p>x</p></body>')
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "no <html> element found")

    def test_html_inside_script_ignored(self):
        html = ('<script>\n'
                'var s = \'<html lang="en">\';\n</script>\n'
                '<body><p>x</p></body>')
        got = checker.find_lang_problems(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["reason"], "no <html> element found")

    def test_real_html_after_commented_one_found(self):
        html = ('<!-- <html lang="fr"> -->\n<html lang="en">')
        self.assertEqual(checker.find_lang_problems(html), [])

    def test_other_attributes_ignored(self):
        html = ('<html lang="en" dir="ltr" data-x="1">')
        self.assertEqual(checker.find_lang_problems(html), [])

    def test_lang_checked_even_with_other_bad_html(self):
        html = '<html lang="en"><body><div><span>oops'
        self.assertEqual(checker.find_lang_problems(html), [])


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html", '<html lang="en">')
            bad, err = checker.check_file(path)
            self.assertEqual((bad, err), ([], None))

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<html>')
            bad, err = checker.check_file(path)
            self.assertIsNone(err)
            self.assertEqual(len(bad), 1)

    def test_no_html_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "plain.html", '<p>no html element</p>')
            bad, err = checker.check_file(path)
            self.assertIsNone(err)
            self.assertEqual(len(bad), 1)
            self.assertEqual(bad[0]["reason"], "no <html> element found")

    def test_missing_file_reports_error(self):
        bad, err = checker.check_file("/nonexistent/page.html")
        self.assertEqual(bad, [])
        self.assertIsNotNone(err)

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<html lang="e\xffn">')
            bad, err = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertEqual(err, "not valid UTF-8")

    def test_input_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = '<html>'
            path = write(tmp, "bad.html", text)
            checker.check_file(path)
            self.assertEqual(Path(path).read_text(), text)


class TestCollectFiles(unittest.TestCase):
    def test_direct_file_any_name_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "page.txt", '<html>')
            self.assertEqual(checker.collect_files([path]), [path])

    def test_folder_walk_finds_html_and_htm_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            b = write(tmp, "sub/b.htm", "")
            write(tmp, "c.md", "")
            write(tmp, "d.txt", "")
            got = checker.collect_files([tmp])
            self.assertEqual(got, sorted([a, b]))

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/sample.html", "")
            a = write(tmp, "a.html", "")
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "sub/b.html", "")
            self.assertEqual(
                checker.collect_files([tmp], recursive=False), [a])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "skip.html", "")
            got = checker.collect_files([tmp], exclude=["skip.html"])
            self.assertEqual(got, [a])

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            checker.collect_files(["/nonexistent/path"])

    def test_duplicates_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", "")
            self.assertEqual(
                checker.collect_files([path, path]), [path])


class TestRun(unittest.TestCase):
    def test_clean_run_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html", '<html lang="en">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn(
                "OK — 1 file(s) checked, every page has a lang "
                "attribute.", out)

    def test_dirty_run_exit_1_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<html>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            # CWD-robust: assert on the file name and message, never
            # on the absolute path the CLI echoes.
            self.assertIn("bad.html", out)
            self.assertIn("<html> line 1 is missing the lang attribute",
                          out)
            self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_malformed_lang_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<html lang="english">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn('has a malformed lang value "english"', out)

    def test_empty_lang_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<html lang="">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("has an empty lang attribute", out)

    def test_no_html_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "plain.html", '<p>no html element</p>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("no <html> element found", out)

    def test_folder_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.html", '<html lang="en">')
            write(tmp, "bad.html", '<html>')
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<html>\n<html lang="english">')
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["problems"], 2)
            self.assertEqual(
                os.path.basename(data["files"][0]["path"]), "bad.html")
            self.assertEqual(
                data["files"][0]["problems"][0]["reason"],
                "missing lang attribute")
            self.assertEqual(
                data["files"][0]["problems"][1]["reason"],
                "malformed lang value")
            self.assertEqual(
                data["files"][0]["problems"][1]["lang"], "english")
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO('<html lang="en">')
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn(
            "OK — 1 file(s) checked, every page has a lang "
            "attribute.", out)

    def test_stdin_dirty_via_main(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO('<html>')
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL <stdin>: <html> line 1 is missing the lang attribute",
            out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "x.html"])
        self.assertEqual(code, 2)
        self.assertIn("--stdin takes no file", err)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("at least one HTML file", err)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/nonexistent/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no HTML files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("html_lang_checker 1.0.0", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<html lang="e\xffn">')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/html_lang_checker.py",
             "examples/good.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/html_lang_checker.py",
             "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/html_lang_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 3 problem(s) in 2 file(s).",
                      folder.stdout)
        self.assertIn("Checked 3 file(s), 3 problem(s) in 2 file(s).",
                      readme)
        js = subprocess.run(
            [sys.executable, "src/html_lang_checker.py",
             "--json", "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_secrets(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore").lower()
            for marker in ("api_key", "api-key", "password", "secret=",
                           "token="):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        src = REPO / "src/html_lang_checker.py"
        tree = ast.parse(src.read_text())
        stdlib = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported - stdlib, imported)
        self.assertNotIn("yaml", imported)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_html_lang_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)


if __name__ == "__main__":
    unittest.main()
