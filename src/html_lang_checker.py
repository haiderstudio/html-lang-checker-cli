#!/usr/bin/env python3
"""Check HTML files carry a lang attribute on the <html> element.

Run: python3 src/html_lang_checker.py page.html
     python3 src/html_lang_checker.py site/
     python3 src/html_lang_checker.py --stdin < page.html

A page with no lang attribute makes a screen reader guess the
language and mispronounce everything on the page. It is the
most common automated accessibility failure on the web (the
axe rule html-has-lang), and the fix is one attribute per
page — but nothing stops you shipping a page without it.
This tool finds every HTML file missing a lang attribute on
its <html> element, or carrying an empty or malformed value,
and reports each one with the file and the line, so it can
fail a CI run before the page ships.

A lang value counts as valid when it looks like a language
tag: a two- or three-letter language code (en, de, zh), an
optional four-letter script (Hans, Latn), an optional
two-letter region or three-digit region (US, GB, 419), and
optional variant parts. So en, en-US, zh-Hans, zh-Hans-CN,
de, and de-1996 all pass, while "english", "e", "en_US",
and "en-" all fail. A lang attribute on any other element —
a <body> or a <div>, say — does not count: only the <html>
element's lang matters to a screen reader.

It never rewrites a file, never touches the network, and
reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

__version__ = "1.0.0"

HTML_EXTENSIONS = {".html", ".htm"}

# A language tag: 2-3 letter language, optional 4-letter
# script, optional 2-letter or 3-digit region, optional
# variant parts (5-8 letters/digits, or a digit plus 3).
LANG_RE = re.compile(
    r"^[A-Za-z]{2,3}"
    r"(-[A-Za-z]{4})?"
    r"(-([A-Za-z]{2}|[0-9]{3}))?"
    r"(-([A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*$"
)


def is_valid_lang(value):
    """True when value looks like a language tag (en, en-US)."""
    return bool(LANG_RE.match(value.strip()))


class _HtmlCollector(HTMLParser):
    """Collect one problem per <html> element with a bad lang."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []
        self.seen_html = False

    def _check_html(self, attrs):
        line, _ = self.getpos()
        self.seen_html = True
        values = {name: value for name, value in attrs}
        lang = values.get("lang")
        if lang is None:
            self.problems.append(
                {"line": line, "lang": None,
                 "reason": "missing lang attribute"})
        elif lang.strip() == "":
            self.problems.append(
                {"line": line, "lang": lang,
                 "reason": "empty lang attribute"})
        elif not is_valid_lang(lang):
            self.problems.append(
                {"line": line, "lang": lang,
                 "reason": "malformed lang value"})

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self._check_html(attrs)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def find_lang_problems(text):
    """Return a list of lang problems in one HTML document.

    Each entry is {"line": int or None, "lang": str or None,
    "reason": str}. Entries are in document order. A document
    with no <html> element at all gets one problem saying so.
    A document whose <html> element carries a valid lang gets
    none.
    """
    collector = _HtmlCollector()
    collector.feed(text)
    collector.close()
    if not collector.seen_html:
        return [{"line": None, "lang": None,
                 "reason": "no <html> element found"}]
    return collector.problems


def check_text(text, path):
    """Check one document's text. Returns (problems, error)."""
    try:
        return find_lang_problems(text), None
    except Exception as exc:  # a malformed document must fail, not crash
        return [], "could not parse: %s" % exc


def check_file(path):
    """Check one file. Returns (problems, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text, str(path))


def _is_html_file(path):
    return Path(path).suffix.lower() in HTML_EXTENSIONS


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of HTML files to check.

    A file given directly is always checked, whatever its name. A
    folder is walked for .html/.htm files. .git folders are never
    walked, and directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(root) / name
                    if not _is_html_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_problem(path, problem):
    """One human-readable line for one lang problem."""
    reason = problem["reason"]
    if reason == "no <html> element found":
        return "FAIL %s: no <html> element found" % path
    if reason == "missing lang attribute":
        return ("FAIL %s: <html> line %d is missing the lang "
                "attribute" % (path, problem["line"]))
    if reason == "empty lang attribute":
        return ("FAIL %s: <html> line %d has an empty lang "
                "attribute" % (path, problem["line"]))
    return ('FAIL %s: <html> line %d has a malformed lang value '
            '"%s"' % (path, problem["line"], problem["lang"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no HTML files found", file=sys.stderr)
        return 2
    results = []
    problems = 0
    files_with_problems = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            problems += count
            files_with_problems += 1
        results.append({"path": path, "problems": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "problems": problems},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for problem in result["problems"]:
                print(format_problem(result["path"], problem))
        if problems:
            print("Checked %d file(s), %d problem(s) in %d file(s)."
                  % (len(files), problems, files_with_problems))
        else:
            print("OK — %d file(s) checked, every page has a lang "
                  "attribute." % len(files))
    return 1 if problems else 0


def run_stdin(as_json=False):
    """Check one HTML document read from standard input."""
    text = sys.stdin.read()
    bad, error = check_text(text, "<stdin>")
    problems = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "problems": bad,
                        "error": error}],
             "checked": 1, "problems": problems},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for problem in bad:
            print(format_problem("<stdin>", problem))
        if problems:
            print("Checked 1 file(s), %d problem(s) in 1 file(s)."
                  % problems)
        else:
            print("OK — 1 file(s) checked, every page has a lang "
                  "attribute.")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_lang_checker",
        description="Check HTML files carry a lang attribute on the "
                    "<html> element, fail CI when one is missing.")
    parser.add_argument("paths", nargs="*", help="HTML files or folders")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one HTML file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
