"""从环境变量加载运行配置（对齐参考项目的 config 层职责）。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _split_categories(raw: str) -> list[str]:
    parts = [x.strip() for x in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _env_flag(key: str, *, default: bool = True) -> bool:
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class Settings:
    feishu_webhook_url: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    arxiv_categories: list[str]
    arxiv_hours: int
    max_papers: int
    arxiv_request_delay: float
    arxiv_http_timeout: float
    arxiv_fetch_html_fulltext: bool
    arxiv_fulltext_context_max_chars: int
    arxiv_html_fetch_timeout: float
    llm_timeout: float
    llm_max_concurrent: int

    @staticmethod
    def load() -> "Settings":
        webhook = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
        key = os.environ.get("OPENAI_API_KEY", "my_llm").strip()
        base = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
        model = os.environ.get("OPENAI_MODEL", "Qwen3-8B").strip()
        cats = _split_categories(os.environ.get("ARXIV_CATEGORIES", "cs.AI,cs.CL"))
        hours = int(os.environ.get("ARXIV_HOURS", "25"))
        max_papers = int(os.environ.get("MAX_PAPERS", "30"))
        delay = float(os.environ.get("ARXIV_REQUEST_DELAY", "3.0"))
        arxiv_http_timeout = float(os.environ.get("ARXIV_HTTP_TIMEOUT", "90"))
        fetch_html = _env_flag("ARXIV_FETCH_HTML_FULLTEXT", default=True)
        fulltext_max = int(os.environ.get("ARXIV_FULLTEXT_CONTEXT_MAX_CHARS", "16000"))
        html_timeout = float(os.environ.get("ARXIV_HTML_FETCH_TIMEOUT", "40"))
        llm_timeout = float(os.environ.get("LLM_TIMEOUT", "120"))
        llm_conc = int(os.environ.get("LLM_MAX_CONCURRENT", "4"))
        return Settings(
            feishu_webhook_url=webhook,
            openai_api_key=key,
            openai_base_url=base,
            openai_model=model,
            arxiv_categories=cats,
            arxiv_hours=max(1, hours),
            max_papers=max(1, max_papers),
            arxiv_request_delay=max(0.5, delay),
            arxiv_http_timeout=max(15.0, arxiv_http_timeout),
            arxiv_fetch_html_fulltext=fetch_html,
            arxiv_fulltext_context_max_chars=max(2000, fulltext_max),
            arxiv_html_fetch_timeout=max(10.0, html_timeout),
            llm_timeout=max(10.0, llm_timeout),
            llm_max_concurrent=max(1, llm_conc),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.feishu_webhook_url:
            errors.append("缺少 FEISHU_WEBHOOK_URL")
        if not self.openai_api_key:
            errors.append("缺少 OPENAI_API_KEY")
        if not self.arxiv_categories:
            errors.append("ARXIV_CATEGORIES 为空")
        return errors
