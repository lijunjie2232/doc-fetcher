"""Minimal self-check for the pure crawler logic (no network). Run: python test_doc_fetcher.py"""
from doc_fetcher.crawler import DocFetcher, canonicalize, is_asset, sitemap_locs

f = DocFetcher("https://flet.dev/docs", "/tmp/out")

# canonicalize: absolute, no fragment/query/trailing slash, lowercased host
assert canonicalize("https://FLET.dev/docs/getting-started/#sec?x=1") == "https://flet.dev/docs/getting-started"
assert canonicalize("/docs/b/", "https://flet.dev/docs") == "https://flet.dev/docs/b"

# prefix rule: only the base path and its descendants match
assert f._in_prefix("https://flet.dev/docs")
assert f._in_prefix("https://flet.dev/docs/quick/start")
assert not f._in_prefix("https://flet.dev")            # parent
assert not f._in_prefix("https://flet.dev/blog")       # sibling
assert not f._in_prefix("https://flet.dev/docsfoo")    # sneaky prefix
assert not f._in_prefix("https://studio.flet.dev/docs")  # other host

# URL -> output file path (compared as segments: Windows uses a different separator)
assert f._dest("https://flet.dev/docs/quick/start").parts[-4:] == ("out", "docs", "quick", "start.md")
assert f._dest("https://flet.dev/docs").name == "docs.md"
assert f._dest("https://flet.dev/docs/index.html").parts[-2:] == ("docs", "index.md")
assert ".." not in f._dest("https://flet.dev/docs/../../etc/passwd").parts

# links to crawled pages are rewritten relative to the saved file; anchors,
# assets and out-of-scope pages keep their absolute URL
page = "https://flet.dev/docs/quick/other"
md = ("[a](https://flet.dev/docs/quick/start#install) [b](/docs) [c](https://flet.dev/blog) "
      "![i](https://flet.dev/docs/logo.png) [d](#sec) [e](https://flet.dev/docs/quick/other#note)")
assert f._relativize(md, page, f._dest(page)) == (
    "[a](start.md#install) [b](../../docs.md) [c](https://flet.dev/blog) "
    "![i](https://flet.dev/docs/logo.png) [d](#sec) [e](#note)"
)

# non-page resources are ignored rather than reported as failures
assert is_asset("https://docs.langchain.com/llms.txt")
assert is_asset("https://flet.dev/docs/logo.PNG")
assert not is_asset("https://flet.dev/docs/v1.2")
assert not is_asset("https://flet.dev/docs/quick/start")

# sitemap parsing: namespaces stripped, index vs. urlset distinguished
urlset = b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\
  <url><loc>https://flet.dev/docs/a</loc></url><url><loc> https://flet.dev/docs/b </loc></url></urlset>'
assert sitemap_locs(urlset) == ("urlset", ["https://flet.dev/docs/a", "https://flet.dev/docs/b"])
index = b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://flet.dev/docs/sitemap.xml</loc></sitemap></sitemapindex>'
assert sitemap_locs(index) == ("sitemapindex", ["https://flet.dev/docs/sitemap.xml"])

# HTML -> Markdown strips inert HTML/JS containers (<template>, <script>, <style>, <iframe>, comments)
sample_html = """<!doctype html><html><head><style>body{color:red}</style></head><body>
<!-- hidden comment -->
<main><h1>Hello Docs</h1><p>Read <a href="/docs/next">next</a>.</p></main>
<script>window.__DATA__ = {"secret": 1};</script>
<template id="mint-config">{"docsConfig":{"name":"Leak"}}</template>
<template data-mint="manifest">{"compiledSource":"function MDX(){}"}</template>
<iframe src="/embed">fallback iframe text</iframe>
</body></html>"""
md_out, hrefs = f._extract(sample_html, "https://flet.dev/docs")
assert "Hello Docs" in md_out
assert "docsConfig" not in md_out and "compiledSource" not in md_out
assert "__DATA__" not in md_out and "color:red" not in md_out
assert "fallback iframe text" not in md_out and "hidden comment" not in md_out
assert any(h.endswith("/docs/next") for h in hrefs)

print("self-check OK")
