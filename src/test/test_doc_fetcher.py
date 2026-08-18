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

# URL -> output file path
assert str(f._dest("https://flet.dev/docs/quick/start")).endswith("out/docs/quick/start.md")
assert str(f._dest("https://flet.dev/docs")).endswith("out/docs.md")
assert str(f._dest("https://flet.dev/docs/index.html")).endswith("out/docs/index.md")
assert ".." not in str(f._dest("https://flet.dev/docs/../../etc/passwd"))

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

print("self-check OK")
