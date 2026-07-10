import argparse
import asyncio
import subprocess
import sys


__INIT_CMD__ = (
    ["crawl4ai-setup"],
    ["crawl4ai-doctor"],
)


def run_init() -> None:
    """Initialize the bundled crawl4ai package.

    Runs ``crawl4ai-setup`` (installs the browser/runtime assets) followed by
    ``crawl4ai-doctor`` (verifies the installation).
    """
    for cmd in (__INIT_CMD__):
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            sys.exit(f"error: command not found: {cmd[0]}")
        except subprocess.CalledProcessError as exc:
            sys.exit(f"error: {cmd[0]} failed with exit code {exc.returncode}")


def main() -> None:
    from .crawler import DocFetcher, DEFAULT_PARALLEL

    ap = argparse.ArgumentParser(prog="doc-fetcher", description="Crawl a docs site into local Markdown.")
    ap.add_argument("url", help="start URL, e.g. https://flet.dev/docs (only <url>/* is fetched)")
    ap.add_argument("out", help="output directory for the Markdown files")
    ap.add_argument("-p", "--parallel", type=int, default=DEFAULT_PARALLEL, help="concurrent fetches [env PARALLEL_NUM]")
    ap.add_argument("--timeout", type=float, default=20.0, help="per-request timeout seconds")
    ap.add_argument("--max-pages", type=int, default=0, help="stop after N pages (0 = unlimited)")
    ap.add_argument("--overwrite", action="store_true", help="refetch pages already saved")
    a = ap.parse_args()

    fetcher = DocFetcher(a.url, a.out, parallel=a.parallel, timeout=a.timeout,
                         overwrite=a.overwrite, max_pages=a.max_pages)
    asyncio.run(fetcher.run())
    print(f"done: {fetcher.scraped} saved, {fetcher.skipped} skipped, {len(fetcher.failed)} failed -> {a.out}")
    for url, err in fetcher.failed[:10]:
        print(f"  fail {url}: {err}")
