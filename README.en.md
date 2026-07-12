# doc_fetcher

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue?style=flat-square">
  <img alt="Runtime" src="https://img.shields.io/badge/runtime-no%20browser-brightgreen?style=flat-square">
</p>

<p align="center">
  <a href="README.md">日本語</a> · <b>English</b> · <a href="README.zh.md">中文</a>
</p>

A documentation crawler for LLMs. Point it at a URL such as `https://flet.dev/docs`
and it fetches every page under that path — and only that path — saving each as a
`.md` file that mirrors the site's URL structure.

HTML→Markdown conversion is provided by [crawl4ai](https://github.com/unclecode/crawl4ai),
driven over plain HTTP (no headless browser) for speed.

---

## How it works

- **Prefix-scoped.** Starting from `<url>`, only same-host descendants of the base
  path (`<url>/*`) are crawled. Sibling pages (`https://flet.dev/abc`), the parent
  (`https://flet.dev`) and other hosts (`studio.flet.dev`) are never fetched.
- **Breadth-first over a queue.** A single shared `httpx.AsyncClient` (keep-alive
  connection pool) is consumed by `PARALLEL_NUM` concurrent workers pulling URLs from
  an `asyncio.Queue`.
- **Skips what's already saved.** Pages whose `.md` already exists are not
  re-downloaded. A `.urls.txt` manifest in the output directory records every URL ever
  discovered, so re-running resumes an interrupted crawl and only fetches the gaps.

## Install

The project uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync                 # create/refresh the venv (.venv) and install dependencies
source .venv/bin/activate
```

Initialize crawl4ai's runtime assets (installs the browser and verifies it):

```bash
fetcher-init            # runs: crawl4ai-setup && crawl4ai-doctor
```

> This crawler only parses fetched HTML, so it runs without a browser; `fetcher-init`
> matters only if you later switch to JS-rendered crawling.

## Usage

```bash
doc-fetcher URL OUT_DIR [-p N] [--timeout S] [--max-pages N] [--overwrite]
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `URL` | — | start page, e.g. `https://flet.dev/docs` (only `URL/*` is crawled) |
| `OUT_DIR` | — | directory for the Markdown files |
| `-p`, `--parallel` | `5` (env `PARALLEL_NUM`) | number of concurrent fetches |
| `--timeout` | `20.0` | per-request timeout in seconds |
| `--max-pages` | `0` | stop after N pages (`0` = unlimited) |
| `--overwrite` | off | re-fetch and rewrite pages already saved |

Examples:

```bash
doc-fetcher https://flet.dev/docs ./flet-docs
PARALLEL_NUM=8 doc-fetcher https://flet.dev/docs ./flet-docs

# without installing the console script, run from source:
PYTHONPATH=src .venv/bin/python -c \
  "import sys; sys.argv=['','https://flet.dev/docs','./flet-docs']; from doc_fetcher import main; main()"
```

A `tqdm` bar shows live progress (`ok` / `skip` / `err` / queue size), followed by a
one-line summary:

```
done: 47 saved, 9 skipped, 0 failed -> ./flet-docs
```

## Output

```
flet-docs/
├── .urls.txt                             # discovery manifest (drives skip/resume)
├── docs.md                               # https://flet.dev/docs
└── docs/
    ├── getting-started/installation.md   # .../docs/getting-started/installation
    └── reference.md
```

Each file is prefixed with a small front-matter block recording its source URL:

```markdown
---
source: https://flet.dev/docs/getting-started/installation
---

...
```

## Notes & limits

- **Static HTML only.** Pages are fetched with `httpx`, so JavaScript-rendered content
  won't appear. Most documentation sites (MkDocs, Docusaurus, Sphinx) are static and
  work fine; JS-heavy sites need crawl4ai's browser mode instead.
- **Query strings are ignored** when canonicalizing URLs, so `/a?x=1` and `/a` are
  treated as one page.
- **Markdown keeps nav/sidebar text.** To drop boilerplate, pass a content filter to
  crawl4ai's `DefaultMarkdownGenerator` and use `fit_markdown`.

## Tests

```bash
.venv/bin/python src/test/test_doc_fetcher.py   # offline checks for prefix/URL/file mapping
```

## Acknowledgements

- [crawl4ai](https://github.com/unclecode/crawl4ai) — the HTML→Markdown foundation.
- [httpx](https://github.com/encode/httpx) — async HTTP with a keep-alive connection pool.
- [tqdm](https://github.com/tqdm/tqdm) — progress display.
- [uv](https://docs.astral.sh/uv/) — dependency and build management.

## Disclaimer

- This tool is intended for fetching public documentation. Always respect the target site's terms of service, `robots.txt`, and rate limits.
- You are responsible for the lawful use of anything you download; check with the site operator before heavy or commercial crawling.
- The software is provided "as is", without warranty of any kind, express or implied.

## License

Distributed under the [GPL-3.0](LICENSE) license.
