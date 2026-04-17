"""OpenAI 兼容 Chat Completions：读摘要 + 可选全文上下文并输出结构化 JSON。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from src.config.settings import Settings
from src.data_fetchers.arxiv import fetch_arxiv_html_context
from src.models.paper import Paper, PaperBriefAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 arXiv 论文精读助手。只根据用户提供的信息归纳，不要编造实验数值或未出现的内容。
如果提供了全文章节上下文，优先基于章节信息给出更细致结论。
输出必须是严格 JSON 对象，键为：overview, motivation, method, deep_reading, takeaway。使用中文。"""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("响应中未找到 JSON 对象")
    return json.loads(m.group())


async def analyze_paper(
    client: httpx.AsyncClient,
    settings: Settings,
    paper: Paper,
    fulltext_context: str | None = None,
    fulltext_status: str | None = None,
    html_url: str | None = None,
) -> PaperBriefAnalysis:
    fulltext_block = ""
    if fulltext_context:
        fulltext_block = (
            f"\n全文来源: {html_url or 'N/A'}\n"
            f"全文解析状态: {fulltext_status or 'success'}\n"
            "以下是按章节抽取的全文片段（可能已截断）：\n"
            f"{fulltext_context}\n"
        )
    else:
        fulltext_block = f"\n全文解析状态: {fulltext_status or 'not_available'}\n"

    user = (
        f"论文 arXiv ID: {paper.id}\n"
        f"标题: {paper.title}\n"
        f"分类: {paper.primary_category}\n"
        f"摘要:\n{paper.abstract}\n"
        f"{fulltext_block}"
        "请返回 JSON：overview, motivation, method, deep_reading, takeaway。\n"
        "要求：deep_reading 必须体现你对方法细节/实验设计/局限性的仔细阅读结论；若全文不可用，请明确写“基于摘要推断”。"
    )
    url = f"{settings.openai_base_url}/chat/completions"
    payload = {
        "model": settings.openai_model,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    r = await client.post(url, headers=headers, json=payload, timeout=settings.llm_timeout)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    obj = _extract_json_object(content)
    return PaperBriefAnalysis.model_validate(obj)


async def analyze_papers_bounded(
    settings: Settings,
    papers: list[Paper],
) -> list[tuple[Paper, PaperBriefAnalysis | None, str | None]]:
    """并发分析多篇论文，返回 (论文, 分析, 错误信息)。"""
    llm_sem = asyncio.Semaphore(settings.llm_max_concurrent)
    html_sem = asyncio.Semaphore(max(1, min(2, settings.llm_max_concurrent)))

    async def _fetch_fulltext(paper: Paper) -> tuple[str | None, str, str | None]:
        if not settings.arxiv_fetch_html_fulltext:
            return None, "disabled", None
        try:
            async with html_sem:
                html_url, context = await fetch_arxiv_html_context(
                    paper.id,
                    timeout=settings.arxiv_html_fetch_timeout,
                    max_chars=settings.arxiv_fulltext_context_max_chars,
                )
            logger.info(
                "全文解析成功 paper_id=%s html_url=%s fallback_to_abstract=false",
                paper.id,
                html_url,
            )
            return context, "success", html_url
        except Exception as e:
            logger.info(
                "全文解析失败 paper_id=%s error=%s fallback_to_abstract=true",
                paper.id,
                e,
            )
            return None, f"failed: {e}", None

    async def one(
        hc: httpx.AsyncClient, p: Paper
    ) -> tuple[Paper, PaperBriefAnalysis | None, str | None]:
        try:
            fulltext_context, fulltext_status, html_url = await _fetch_fulltext(p)
            async with llm_sem:
                a = await analyze_paper(
                    hc,
                    settings,
                    p,
                    fulltext_context=fulltext_context,
                    fulltext_status=fulltext_status,
                    html_url=html_url,
                )
            return (p, a, None)
        except Exception as e:
            logger.warning("LLM 分析失败 %s: %s", p.id, e)
            return (p, None, str(e))

    async with httpx.AsyncClient(trust_env=True) as hc:
        return list(await asyncio.gather(*[one(hc, p) for p in papers]))
