# arXiv Daily Feishu

`arxiv-daily-feishu` 是一个每日自动化流程：抓取 arXiv 新论文 -> 调用 LLM 生成中文阅读笔记 -> 推送飞书卡片。

当前版本支持“仔细阅读”模式：优先抓取 arXiv 官方 HTML 全文，提取章节上下文后参与分析；若某篇 HTML 不可用（如 404），自动回退为摘要模式，不影响整批任务继续执行。

## 功能概览

- 按分类抓取 arXiv 论文（分页、限流、重试）
- 本地 `seen_ids` 去重，避免重复推送
- LLM 结构化输出（概述、问题、方法、精读、要点）
- 飞书分批卡片推送
- HTML 全文调试工具（可落盘原始 HTML 与清洗结果）

## 项目结构

```text
arxiv-daily-feishu/
├── src/
│   ├── data_fetchers/
│   │   ├── arxiv/client.py         # arXiv API 抓取
│   │   ├── arxiv/html_fulltext.py  # 官方 HTML 全文抓取与清洗
│   │   └── seen_ids.py             # 已推送 ID 持久化
│   ├── llm/paper_reader.py         # LLM 分析（含 HTML 精读上下文）
│   ├── notifiers/feishu.py         # 飞书卡片组装与发送
│   ├── pipeline/daily.py           # 主流水线
│   └── __main__.py                 # CLI 入口（python -m src）
├── scripts/
│   ├── daily_arxiv.py              # 兼容入口（复用主 CLI）
│   └── test_html_fetch.py          # HTML 中间测试脚本
├── data/
│   └── debug/                      # 调试输出（原始 HTML / 清洗结果）
└── .env.example
```

## 快速开始

1) 安装依赖

```bash
pip install -r requirements.txt
```

2) 配置环境变量

```bash
cp .env.example .env
# 按需修改 .env
```

3) 执行每日任务

```bash
set -a && source .env && set +a && python -m src
```

## 环境变量说明

### 必填项

- `FEISHU_WEBHOOK_URL`：飞书机器人 webhook
- `OPENAI_API_KEY`：OpenAI 兼容接口 key
- `OPENAI_BASE_URL`：OpenAI 兼容接口地址
- `OPENAI_MODEL`：模型名

### arXiv 抓取

- `ARXIV_CATEGORIES`：分类列表，逗号分隔（如 `cs.AI,cs.CL,cs.CV,cs.LG`）
- `ARXIV_HOURS`：时间窗（小时）
- `MAX_PAPERS`：单次最多处理篇数
- `ARXIV_REQUEST_DELAY`：arXiv 请求间隔（秒）
- `ARXIV_HTTP_TIMEOUT`：arXiv API 超时（秒）

### HTML 精读

- `ARXIV_FETCH_HTML_FULLTEXT`：是否开启 HTML 全文抓取（默认 `true`）
- `ARXIV_FULLTEXT_CONTEXT_MAX_CHARS`：传给 LLM 的清洗后上下文最大字符数（默认 `16000`）
- `ARXIV_HTML_FETCH_TIMEOUT`：HTML 抓取超时（秒，默认 `40`）

### LLM 调用

- `LLM_TIMEOUT`：单次 LLM 调用超时（秒）
- `LLM_MAX_CONCURRENT`：LLM 最大并发数

### 可选项

- `PROXY_URL`：统一代理地址，会自动同步到 `http_proxy`/`https_proxy`
- `SEND_ON_EMPTY`：无新论文时是否推送空卡片（`true/false`）
- `FEISHU_CHUNK_SIZE`：每条飞书卡片包含论文数（默认 `6`）

## HTML 是怎么抓和清洗的

实现位置：`src/data_fetchers/arxiv/html_fulltext.py`

- 先查 arXiv API 的 `entry.id` 获取最新版本号 `vN`
- 请求 `https://arxiv.org/html/{paper_id}{vN}`
- 用 `BeautifulSoup` 删除 `script/style/noscript`
- 从 `main -> article -> #content -> body` 选择正文根节点
- 只提取 `h2/h3/h4` 和 `p`，按标题边界组章节
- 规范化空白，限制每章段落数，并按 `max_chars` 截断

若 HTML 不可访问（如 `404`），日志会记录：
- `fallback_to_abstract=true`

该篇会自动降级为摘要分析，不中断整批执行。

## 中间测试（推荐）

可单独验证“抓到了什么 HTML”和“清洗后是什么”：

```bash
set -a && source .env && set +a && python scripts/test_html_fetch.py
```

可指定论文：

```bash
set -a && source .env && set +a && python scripts/test_html_fetch.py --paper-id 2604.15309
```

输出文件在 `data/debug/`：

- `*.raw.html`：原始 HTML
- `*.cleaned.md`：清洗后上下文（LLM 输入近似形态）

## 运行与排障

- 看日志里的 `fallback_to_abstract=true` 可快速定位 HTML 回退数量
- 若频繁超时，优先检查：
  - 代理是否可用
  - `ARXIV_REQUEST_DELAY` 是否过低
  - `ARXIV_HTML_FETCH_TIMEOUT` 是否过短
- 若 LLM 返回格式异常，先确认模型支持稳定 JSON 输出

## 开发说明

- 主入口：`python -m src`
- 兼容入口：`python scripts/daily_arxiv.py`（内部复用主入口逻辑）
- 语法检查：

```bash
python -m compileall src scripts
```
