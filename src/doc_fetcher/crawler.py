"""Prefix-scoped documentation crawler: fetch web pages over plain HTTP and
save each as Markdown (via crawl4ai) into a directory tree.

Design: a single shared ``httpx.AsyncClient`` (keep-alive connection pool) is
consumed by ``parallel`` worker coroutines pulling URLs from an ``asyncio.Queue``.
Only URLs matching ``<base_url>/*`` (same host, path under the base path) are ever
fetched; pages already on disk are skipped.
"""
from __future__ import annotations

import asyncio
import os
import urllib.parse as up
from pathlib import Path
from typing import Set

import httpx
from tqdm import tqdm

from crawl4ai import DefaultMarkdownGenerator, LXMLWebScrapingStrategy

_UA = "Mozilla/5.0 (compatible; doc-fetcher/0.1)"
DEFAULT_PARALLEL = int(os.environ.get("PARALLEL_NUM", "5"))


def canonicalize(url: str, base: str = "") -> str:
    """Absolute, fragment/query-free, trailing-slash-free URL used for dedup."""
    if base:
        url = up.urljoin(base, url)
    url, _ = up.urldefrag(url)
    s = up.urlsplit(url)
    return up.urlunsplit((s.scheme.lower(), s.netloc.lower(), s.path.rstrip("/"), "", ""))


class DocFetcher:
    def __init__(
        self,
        start_url: str,
        out_dir: str | os.PathLike,
        parallel: int = DEFAULT_PARALLEL,
        timeout: float = 20.0,
        overwrite: bool = False,
        max_pages: int = 0,
    ):
        s = up.urlsplit(start_url)
        if s.scheme not in ("http", "https") or not s.netloc:
            raise ValueError(f"start_url must be absolute http(s), got {start_url!r}")
        self.scheme, self.netloc = s.scheme, s.netloc.lower()
        self.base_path = s.path.rstrip("/")  # "/docs"; "" means whole site
        self.start = canonicalize(start_url)
        self.out = Path(out_dir)
        self.parallel = max(1, int(parallel))
        self.timeout = timeout
        self.overwrite = overwrite
        self.max_pages = max_pages  # 0 = unlimited
        self.seen: Set[str] = {self.start}
        self.queue: "asyncio.Queue[str]" = asyncio.Queue()
        self.scraped = self.skipped = 0
        self.failed: list[tuple[str, str]] = []
        self._stop = False
        self._scraper = LXMLWebScrapingStrategy()
        self._md = DefaultMarkdownGenerator()
        # Manifest of every URL ever discovered, so a resumed crawl can skip
        # already-saved pages yet still know (and fetch) the ones not done yet.
        self.manifest_path = self.out / ".urls.txt"
        self._manifest = None

    def _load_seen(self) -> None:
        """Enqueue previously discovered URLs (their file, if present, is skipped later)."""
        if not self.manifest_path.exists():
            return
        for line in self.manifest_path.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if url and url not in self.seen and self._in_prefix(url):
                self.seen.add(url)
                self.queue.put_nowait(url)

    def _discover(self, url: str) -> None:
        self.seen.add(url)
        self.queue.put_nowait(url)
        self._manifest.write(url + "\n")  # ponytail: flushed per line for crash-safe resume
        self._manifest.flush()

    def _in_prefix(self, url: str) -> bool:
        """Keep the start URL and its descendants only: sibling/parent/other-host URLs no."""
        s = up.urlsplit(url)
        if (s.scheme, s.netloc) != (self.scheme, self.netloc):
            return False
        path = s.path or "/"
        if not self.base_path:
            return True
        return path == self.base_path or path.startswith(self.base_path + "/")

    def _dest(self, url: str) -> Path:
        """Map a URL to an output .md path mirroring the URL directory structure."""
        segs = [p for p in up.unquote(up.urlsplit(url).path).split("/") if p not in ("", ".", "..")]
        if not segs:
            segs = ["index"]
        if segs[-1].lower().endswith((".html", ".htm")):
            segs[-1] = segs[-1][: segs[-1].rindex(".")]
        leaf = self.out.joinpath(*segs)
        return leaf.with_name(leaf.name + ".md")

    async def _process(self, url: str, client: httpx.AsyncClient) -> None:
        dest = self._dest(url)
        if dest.exists() and not self.overwrite:
            self.skipped += 1
            return
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - record and move on
            self.failed.append((url, f"{type(exc).__name__}: {exc}"))
            return
        if "html" not in resp.headers.get("content-type", "").lower():
            self.failed.append((url, f"not html: {resp.headers.get('content-type')!r}"))
            return

        final = canonicalize(str(resp.url), url)
        result = self._scraper.scrap(final, resp.text)
        markdown = self._md.generate_markdown(result.cleaned_html, base_url=final).raw_markdown
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"---\nsource: {url}\n---\n\n{markdown}", encoding="utf-8")
        self.scraped += 1

        for link in result.links.internal:
            child = canonicalize(link.href, final)
            if child in self.seen or not self._in_prefix(child):
                continue
            self._discover(child)

    async def _worker(self, client: httpx.AsyncClient, pbar: tqdm) -> None:
        while True:
            url = await self.queue.get()
            try:
                if not self._stop:
                    await self._process(url, client)
            finally:
                self.queue.task_done()
                pbar.update(1)
                pbar.set_postfix(ok=self.scraped, skip=self.skipped, err=len(self.failed), q=self.queue.qsize())
                if self.max_pages and self.scraped >= self.max_pages:
                    self._stop = True

    async def run(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        limits = httpx.Limits(max_connections=self.parallel, max_keepalive_connections=self.parallel)
        # ponytail: HTTP/1.1 keep-alive reuses a pool of <=parallel TCP connections;
        # one truly shared connection needs HTTP/2 (pip install h2, http2=True).
        async with httpx.AsyncClient(
            limits=limits,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"user-agent": _UA, "accept": "text/html,*/*"},
        ) as client:
            with self.manifest_path.open("a", encoding="utf-8") as self._manifest:
                self._load_seen()  # resume: enqueue URLs discovered in prior runs
                self.queue.put_nowait(self.start)
                with tqdm(desc=f"doc-fetch {self.start}", unit="page") as pbar:
                    workers = [asyncio.create_task(self._worker(client, pbar)) for _ in range(self.parallel)]
                    await self.queue.join()
                    for w in workers:
                        w.cancel()
                    await asyncio.gather(*workers, return_exceptions=True)
