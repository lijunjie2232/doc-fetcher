# doc_fetcher

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue?style=flat-square">
  <img alt="Runtime" src="https://img.shields.io/badge/runtime-no%20browser-brightgreen?style=flat-square">
</p>

<p align="center">
  <a href="README.md">日本語</a> · <a href="README.en.md">English</a> · <b>中文</b>
</p>

面向 LLM 的文档站点爬虫。给定一个 URL（例如 `https://flet.dev/docs`），它会抓取该路径下
（且仅限该路径下）的每一个页面，并按站点原有的 URL 结构将其保存为对应的 `.md` 文件。

HTML→Markdown 的转换由 [crawl4ai](https://github.com/unclecode/crawl4ai) 提供，
为追求速度，全程通过纯 HTTP 驱动（无需无头浏览器）。

---

## 工作原理

- **前缀限定。** 从起始 URL `<url>` 出发，仅爬取同主机下基底路径 `<url>/*` 的后代页面。
  同级页面（`https://flet.dev/abc`）、父级（`https://flet.dev`）以及其他主机（`studio.flet.dev`）
  一律不会被抓取。
- **由 `sitemap.xml` 播种。** 抓取前先读取 `<host>/sitemap.xml`（含嵌套的 `sitemapindex`），
  把其中所有在范围内的 URL 入队。由 JS 渲染的文档站（Mintlify、Nextra、客户端导航等）
  静态 HTML 里几乎没有可用的 `<a>` 标签，仅靠跟随链接将一无所获。
- **基于队列的广度优先。** 单个共享的 `httpx.AsyncClient`（keep-alive 连接池）由
  `PARALLEL_NUM` 个并发 worker 消费，它们从 `asyncio.Queue` 中取出 URL。
- **跳过已保存内容。** 对应 `.md` 已存在的页面不会被重复下载。输出目录中的清单文件
  `.urls.txt` 记录了历史上发现过的所有 URL，因此重新运行即可续抓中断的爬取，且仅补齐缺失部分。
- **忽略非 HTML 链接。** `llms.txt`、`sitemap.xml`、PDF、图片等资源会被静默跳过，不再计入失败。

## 安装

本项目使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync                 # 创建/刷新虚拟环境 (.venv) 并安装依赖
source .venv/bin/activate
```

初始化 crawl4ai 的运行时资源（安装浏览器并校验）：

```bash
fetcher-init            # 等价于: crawl4ai-setup && crawl4ai-doctor
```

> 本爬虫只解析抓取到的 HTML，因此无需浏览器即可运行；
> 仅当你日后切换到 JS 渲染抓取时，`fetcher-init` 才有意义。

## 用法

```bash
doc-fetcher URL OUT_DIR [-p N] [--timeout S] [--max-pages N] [--overwrite] [--no-relative-links]
```

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `URL` | — | 起始页面，例如 `https://flet.dev/docs`（仅抓取 `URL/*`） |
| `OUT_DIR` | — | Markdown 文件的输出目录 |
| `-p`, `--parallel` | `5`（环境变量 `PARALLEL_NUM`） | 并发抓取数 |
| `--timeout` | `20.0` | 单请求超时（秒） |
| `--max-pages` | `0` | 抓取 N 个页面后停止（`0` = 不限） |
| `--overwrite` | 关闭 | 重新抓取并覆写已保存的页面 |
| `--no-relative-links` | 关闭（默认相对化） | 正文/大纲中指向抓取范围内页面的链接保持绝对 URL |

示例：

```bash
doc-fetcher https://flet.dev/docs ./flet-docs
PARALLEL_NUM=8 doc-fetcher https://flet.dev/docs ./flet-docs

# 未安装控制台脚本时，直接从源码运行：
PYTHONPATH=src .venv/bin/python -c \
  "import sys; sys.argv=['','https://flet.dev/docs','./flet-docs']; from doc_fetcher import main; main()"
```

`tqdm` 进度条会实时显示进展（`ok` / `skip` / `err` / 队列长度），随后输出一行汇总：

```
done: 47 saved, 9 skipped, 0 failed -> ./flet-docs
```

## 输出

```
flet-docs/
├── .urls.txt                             # 发现清单（驱动跳过/续抓）
├── docs.md                               # https://flet.dev/docs
└── docs/
    ├── getting-started/installation.md   # .../docs/getting-started/installation
    └── reference.md
```

每个文件开头都会带一小段 front-matter，记录其来源 URL：

```markdown
---
source: https://flet.dev/docs/getting-started/installation
---

...
```

正文与侧边栏大纲中的链接，会把指向抓取范围内页面的绝对 URL 改写为相对于
保存文件的路径（例如 `https://flet.dev/docs/quick/start` → `start.md`）。
范围外的 URL、图片等资源、页内锚点（`#id`）保持原样。可用 `--no-relative-links` 关闭。

## 注意事项与限制

- **仅支持静态 HTML。** 页面通过 `httpx` 抓取，因此 JavaScript 渲染的内容不会被获取。
  大多数文档站点（MkDocs、Docusaurus、Sphinx）都是静态的，可正常工作；
  重度依赖 JS 的站点则需改用 crawl4ai 的浏览器模式。页面内容本身由 JS 渲染、
  且站点未提供 `sitemap.xml` 的站，本工具无法发现其页面。
- **规范化 URL 时忽略查询字符串，** 因此 `/a?x=1` 与 `/a` 被视为同一页面。
- **Markdown 会保留导航/侧边栏文本。** 若要去除这些样板内容，
  请向 crawl4ai 的 `DefaultMarkdownGenerator` 传入内容过滤器并使用 `fit_markdown`。

## 测试

```bash
.venv/bin/python src/test/test_doc_fetcher.py   # 针对前缀/URL/文件映射的离线校验
```

## 致谢

- [crawl4ai](https://github.com/unclecode/crawl4ai) —— HTML→Markdown 转换的基础。
- [httpx](https://github.com/encode/httpx) —— 带 keep-alive 连接池的异步 HTTP。
- [tqdm](https://github.com/tqdm/tqdm) —— 进度显示。
- [uv](https://docs.astral.sh/uv/) —— 依赖与构建管理。

## 免责声明

- 本工具面向公开文档的抓取，请务必遵守目标站点的使用条款、`robots.txt` 及访问频率限制。
- 下载内容的合法使用责任由使用者自行承担；在大规模或商用抓取前，建议先与站点方确认。
- 本软件按“现状”提供，不作任何明示或默示的担保。

## 许可证

本项目在 [GPL-3.0](LICENSE) 许可证下发布。
