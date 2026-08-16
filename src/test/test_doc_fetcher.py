"""Minimal self-check for the pure crawler logic (no network). Run: python test_doc_fetcher.py"""
from doc_fetcher.crawler import DocFetcher, canonicalize, is_asset

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

print("self-check OK")
