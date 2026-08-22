# doc_fetcher

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue?style=flat-square">
  <img alt="Runtime" src="https://img.shields.io/badge/runtime-no%20browser-brightgreen?style=flat-square">
</p>

<p align="center">
  <b>日本語</b> · <a href="README.en.md">English</a> · <a href="README.zh.md">中文</a>
</p>

指定した URL（例: `https://flet.dev/docs`）配下のドキュメントサイトを各ページずつ取得し、
サイトの URL 構造を反映した `.md` ファイルとしてローカルへ保存する、LLM 向けのクローラです。
`https://flet.dev/docs` を指定すれば、そのパス配下（かつそのパスのみ）のすべてのページが対象になります。

HTML→Markdown の変換は [crawl4ai](https://github.com/unclecode/crawl4ai) を利用し、
速度のためヘッドレスブラウザではなくプレーンな HTTP で駆動します。

---

## 動作の仕組み

- **プレフィックススコープ** — 開始 URL `<url>` から、同一ホスト上の基底パス配下 `<url>/*` のみをクロールします。
  兄弟ページ（`https://flet.dev/abc`）、親（`https://flet.dev`）、他ホスト（`studio.flet.dev`）は取得対象外です。
- **`sitemap.xml` からシード** — クロール前に `<host>/sitemap.xml`（入れ子の `sitemapindex` を含む）を読み、
  スコープ内の URL をすべてキューに入れます。JS 描画型のドキュメントサイト（Mintlify / Nextra /
  クライアントサイドナビゲーション）は静的 HTML に使える `<a>` をほとんど含まないため、
  リンク追跡だけでは何も見つかりません。
- **キューに対する幅優先探索** — 単一の共有 `httpx.AsyncClient`（キープライブ接続プール）を、
  `asyncio.Queue` から URL を取り出す `PARALLEL_NUM` 個の同時ワーカーが消費します。
- **保存済みはスキップ** — `.md` が既に存在するページは再ダウンロードしません。
  出力ディレクトリのマニフェスト `.urls.txt` が過去に発見した全 URL を記録するため、
  再実行で中断したクロールを再開し、未取得分だけを取得できます。
- **非 HTML リンクは無視** — `llms.txt`・`sitemap.xml`・PDF・画像などのアセットは、
  失敗として報告せず静かにスキップします。

## インストール

本プロジェクトは [uv](https://docs.astral.sh/uv/) を使用します。

```bash
uv sync                 # venv (.venv) を作成・更新し依存関係をインストール
source .venv/bin/activate
```

crawl4ai のランタイムアセットを初期化します（ブラウザのインストールと検証を実行）。

```bash
fetcher-init            # 実行内容: crawl4ai-setup && crawl4ai-doctor
```

> 本クローラは取得済み HTML の解析のみを行うため、ブラウザなしでも動作します。
> `fetcher-init` が必要になるのは、後で JS レンダリング方式のクロールへ切り替える場合に限られます。

## 使い方

```bash
doc-fetcher URL OUT_DIR [-p N] [--timeout S] [--max-pages N] [--overwrite]
```

| オプション | デフォルト | 意味 |
| --- | --- | --- |
| `URL` | — | 開始ページ（例: `https://flet.dev/docs`。`URL/*` のみが対象） |
| `OUT_DIR` | — | Markdown ファイルの出力ディレクトリ |
| `-p`, `--parallel` | `5`（環境変数 `PARALLEL_NUM`） | 同時取得数 |
| `--timeout` | `20.0` | リクエストごとのタイムアウト（秒） |
| `--max-pages` | `0` | N ページ取得で停止（`0` = 無制限） |
| `--overwrite` | off | 保存済みページも再取得して上書き |

実行例:

```bash
doc-fetcher https://flet.dev/docs ./flet-docs
PARALLEL_NUM=8 doc-fetcher https://flet.dev/docs ./flet-docs

# コンソールスクリプトをインストールせず、ソースから実行する場合:
PYTHONPATH=src .venv/bin/python -c \
  "import sys; sys.argv=['','https://flet.dev/docs','./flet-docs']; from doc_fetcher import main; main()"
```

進捗は `tqdm` バーでリアルタイム表示され（`ok` / `skip` / `err` / キュー長）、完了後に 1 行のサマリーを出力します。

```
done: 47 saved, 9 skipped, 0 failed -> ./flet-docs
```

## 出力

```
flet-docs/
├── .urls.txt                             # 発見マニフェスト（スキップ／再開を駆動）
├── docs.md                               # https://flet.dev/docs
└── docs/
    ├── getting-started/installation.md   # .../docs/getting-started/installation
    └── reference.md
```

各ファイルの先頭には、取得元 URL を記録する小さな front-matter が付与されます。

```markdown
---
source: https://flet.dev/docs/getting-started/installation
---

...
```

## 注意事項と制約

- **静的 HTML のみ対応** — ページは `httpx` で取得するため、JavaScript でレンダリングされる内容は取得できません。
  大半のドキュメントサイト（MkDocs / Docusaurus / Sphinx）は静的であり問題なく動作しますが、
  JS 依存の強いサイトは crawl4ai のブラウザモードが必要です。本文が JS 描画で
  かつ `sitemap.xml` を公開していないサイトは、ページを発見できません。
- **クエリ文字列は無視** — URL の正規化時に `/a?x=1` と `/a` は同一ページとして扱われます。
- **Markdown はナビ／サイドバーのテキストを含む** — 定型文を除外するには、crawl4ai の
  `DefaultMarkdownGenerator` にコンテンツフィルタを渡して `fit_markdown` を利用してください。

## テスト

```bash
.venv/bin/python src/test/test_doc_fetcher.py   # プレフィックス／URL／ファイルマッピングのオフライン検証
```

## 謝辞

- [crawl4ai](https://github.com/unclecode/crawl4ai) — HTML→Markdown 変換の基盤。
- [httpx](https://github.com/encode/httpx) — 非同期 HTTP とキープライブ接続プール。
- [tqdm](https://github.com/tqdm/tqdm) — 進捗表示。
- [uv](https://docs.astral.sh/uv/) — 依存関係とビルドの管理。

## 免責事項

- 本ツールは公開ドキュメントの取得を想定していますが、対象サイトの利用規約・`robots.txt`・レート制限を必ず遵守してください。
- 取得物の法的責任は利用者自身に帰属します。商用・大量取得では事前に対象サイトへの確認を推奨します。
- 本ソフトウェアは現状有姿で提供され、明示・黙示を問わずいかなる保証も伴いません。

## ライセンス

本プロジェクトは [GPL-3.0](LICENSE) の下で公開されています。
