# html-lang-checker-cli

Check every HTML file carries a `lang` attribute on the `<html>` element, fail CI when one is missing.

[![CI](https://github.com/haiderstudio/html-lang-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-lang-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_lang_checker` reads HTML files and finds every
`<html>` element missing its `lang` attribute — or
carrying an empty or malformed value — and reports each
one with the file and the line number. It exits 1 when
any page fails, so it can fail a CI run. A file where
every `<html>` element carries a valid lang exits 0.

- A page with no `lang` makes a screen reader guess the
  language and mispronounce everything on the page. It
  is the most common automated accessibility failure on
  the web (the axe rule html-has-lang), and the fix is
  one attribute per page — but nothing stops you
  shipping a page without it. This catches it before
  the page ships.
- A lang value counts as valid when it looks like a
  language tag: a two- or three-letter language code
  (`en`, `de`, `zh`), an optional four-letter script
  (`Hans`, `Latn`), an optional two-letter region or
  three-digit region (`US`, `GB`, `419`), and optional
  variant parts. So `en`, `en-US`, `zh-Hans`,
  `zh-Hans-CN`, `de`, and `de-1996` all pass, while
  `"english"`, `"e"`, `"en_US"`, and `"en-"` all fail.
- A `lang` attribute on any other element does not
  count: `<body lang="en">` with no lang on `<html>`
  still fails, because only the `<html>` element's
  lang tells a screen reader the page language.
- A file with no `<html>` element at all is reported
  too, and so is a file with two `<html>` elements —
  each one is checked on its own line. An `<html>`
  inside an HTML comment, or inside a `<script>` block,
  does not count: only real elements count.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  `.html` and `.htm` files, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are never
  followed.
- `--json` prints the result as JSON (the human-readable
  lines go to standard error), and `--stdin` checks one
  HTML document read from standard input.

## Who it is for

Anyone who owns a website and does not want a screen
reader to guess the language of their pages — front-end
developers, teams that review each other's templates,
and anyone whose pages are written by hand or by a CMS.

## What it does NOT do

- It does not check whether the language tag matches
  the language the page is actually written in. A page
  written in French but tagged `lang="en"` passes —
  whether the tag is true is a different check.
- It does not check alt text, titles, or any other
  accessibility rule. That is the job of the other
  checkers in this series (image-alt-checker-cli for
  alt text, html-title-checker-cli for titles) — the
  page language is a different check on the same pages.
- It does not fetch a live site, and it never rewrites
  a file. It is report-only, and it never touches the
  network.

## How this differs

- A fresh search of GitHub on Nov 12, 2026 found 0
  results for `"html-lang-checker-cli"` and 9 results
  for `html lang checker`. The two closest are named
  honestly below — neither is a tested CLI with a CI
  gate on local files.
- **JayPanoz/lang-checker** (0 stars) is a JavaScript
  utility library for checking langs in (X)HTML files
  — a library you call from your own code, not a
  command-line tool and not a CI gate.
- **tommyt852/website-accessibility-checker** (0 stars)
  crawls a live domain and reports html lang as one
  check among many — it needs a live site, a different
  job from checking local files before they ship.
- Repo #9, seo-meta-audit-skill, checks title, meta,
  canonical, Open Graph, and H1 on one page — it does
  not check `lang`, and it is a skill, not a CLI gate.
  Repo #30, image-alt-checker-cli, checks images; the
  page language is a different check on the same pages.

## Install

```sh
git clone https://github.com/haiderstudio/html-lang-checker-cli.git
cd html-lang-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one HTML file:

```sh
python3 src/html_lang_checker.py page.html
```

A file where the page carries a valid lang passes:

```sh
$ python3 src/html_lang_checker.py examples/good.html
OK — 1 file(s) checked, every page has a lang attribute.
```

A file with pages missing or misusing lang fails, with
the file and line for each one:

```sh
$ python3 src/html_lang_checker.py examples/bad.html
FAIL examples/bad.html: <html> line 2 is missing the lang attribute
FAIL examples/bad.html: <html> line 9 has a malformed lang value "english"
Checked 1 file(s), 2 problem(s) in 1 file(s).
```

Check a whole folder (HTML files only):

```sh
$ python3 src/html_lang_checker.py examples/
FAIL examples/bad.html: <html> line 2 is missing the lang attribute
FAIL examples/bad.html: <html> line 9 has a malformed lang value "english"
FAIL examples/other.html: <html> line 2 is missing the lang attribute
Checked 3 file(s), 3 problem(s) in 2 file(s).
```

Check one document from standard input:

```sh
$ python3 src/html_lang_checker.py --stdin < examples/other.html
FAIL <stdin>: <html> line 2 is missing the lang attribute
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/html_lang_checker.py --json examples/bad.html
{
  "files": [
    {
      "path": "examples/bad.html",
      "problems": [
        {
          "line": 2,
          "lang": null,
          "reason": "missing lang attribute"
        },
        {
          "line": 9,
          "lang": "english",
          "reason": "malformed lang value"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 2
}
```

Exit codes: 0 when every page has a valid lang, 1
when any page is missing a lang or a file cannot be
read, 2 for a usage error (a missing path, a bad flag,
or no HTML files found).

## Examples

A missing lang and a malformed one in the same file —
the `<html>` on line 2 of `examples/bad.html` has no
lang at all, and the second `<html>` on line 9 carries
`"english"`, which is a word, not a language tag:

```sh
$ python3 src/html_lang_checker.py examples/bad.html
FAIL examples/bad.html: <html> line 2 is missing the lang attribute
FAIL examples/bad.html: <html> line 9 has a malformed lang value "english"
Checked 1 file(s), 2 problem(s) in 1 file(s).
```

A lang on the wrong element does not count — in
`examples/other.html` the language sits on `<body>`,
not on `<html>`, so the page still fails:

```sh
$ python3 src/html_lang_checker.py examples/other.html
FAIL examples/other.html: <html> line 2 is missing the lang attribute
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_html_lang_checker.py
```

The tests cover lang values (valid `en`, `de`,
`en-US`, `zh-Hans`, `zh-Hans-CN`, `fil`, `es-419`,
`sr-Latn`, `de-1996`, lowercase regions, uppercase
language, single-quoted, unquoted, spaced, and
self-closing values; malformed `"english"`, `"e"`,
`"en_US"`, `"en-"`, `"123"`, `"en--US"`, and `"engl"`),
the check itself (missing lang with the right line,
empty and whitespace-only lang, lang on a `<body>` or
`<div>` only, uppercase `HTML` and `LANG`, multiple
`<html>` elements each checked, problems in document
order, no `<html>` element at all, an empty file, a
whitespace-only file, malformed HTML tolerated, an
`<html>` inside a comment or `<script>` ignored, a
real `<html>` after a commented one), the CLI (exit
0/1/2, folder walking, `.html` and `.htm` only,
`.git` skipped, `--no-recursive`, `--exclude`, a
direct file checked even without an HTML name,
`--stdin`, `--json` output, `--version`, bad flags,
missing paths, empty folders, a non-UTF-8 file
reported, input files left unchanged), the bundled
examples (sample output compared byte-for-byte against
a fresh run, and the README-quoted outputs checked
against it), and hygiene checks (no placeholder text,
no absolute paths, stdlib imports only, `.env` first
in `.gitignore`, CI file runs the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking the lang attribute is not new — the
axe rule html-has-lang names the same failure — but no
existing tool does this one job as a tested
command-line gate on local files, as the search above
shows, and every line of code here is original, built
on nothing but Python's standard library.
