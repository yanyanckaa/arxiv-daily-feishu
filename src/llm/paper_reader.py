"""OpenAI 兼容 Chat Completions：读标题+摘要并输出结构化 JSON。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from src.config.settings import Settings
from src.models.paper import Paper, PaperBriefAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 arXiv 论文阅读助手。只根据用户提供的标题与摘要进行归纳，不要编造实验数值或未出现的内容。
输出必须是严格 JSON 对象，键为：overview, motivation, method, takeaway。使用中文。"""


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
) -> PaperBriefAnalysis:
    user = (
        f"论文 arXiv ID: {paper.id}\n"
        f"标题: {paper.title}\n"
        f"分类: {paper.primary_category}\n"
        f"摘要:\n{paper.abstract}\n"
        "请返回 JSON：overview, motivation, method, takeaway。"
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
    sem = asyncio.Semaphore(settings.llm_max_concurrent)

    async def one(
        hc: httpx.AsyncClient, p: Paper
    ) -> tuple[Paper, PaperBriefAnalysis | None, str | None]:
        async with sem:
            try:
                a = await analyze_paper(hc, settings, p)
                return (p, a, None)
            except Exception as e:
                logger.warning("LLM 分析失败 %s: %s", p.id, e)
                return (p, None, str(e))

    async with httpx.AsyncClient(trust_env=True) as hc:
        return list(await asyncio.gather(*[one(hc, p) for p in papers]))
