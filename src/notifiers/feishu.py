"""飞书自定义机器人：interactive 卡片（对齐参考项目 notifiers/feishu）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from src.models.paper import Paper, PaperBriefAnalysis

logger = logging.getLogger(__name__)


def _escape_md(text: str) -> str:
    return text.replace("<", "〈").replace(">", "〉")


def build_card(
    *,
    title: str,
    date_str: str,
    sections: list[tuple[Paper, PaperBriefAnalysis | None, str | None]],
) -> dict[str, Any]:
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**日期**: {date_str}\n**本批论文数**: {len(sections)}",
            },
        },
    ]
    if sections:
        elements.append({"tag": "hr"})
    for paper, analysis, err in sections:
        if analysis:
            body = (
                f"**[{paper.id}]** [{paper.title}]({paper.abs_url})\n"
                f"*{paper.primary_category}*\n\n"
                f"**概述** {_escape_md(analysis.overview)}\n\n"
                f"**问题** {_escape_md(analysis.motivation)}\n\n"
                f"**方法** {_escape_md(analysis.method)}\n\n"
                f"**精读** {_escape_md(analysis.deep_reading)}\n\n"
                f"**要点** {_escape_md(analysis.takeaway)}"
            )
        else:
            err_safe = _escape_md((err or "unknown").replace("`", "'")[:200])
            body = (
                f"**[{paper.id}]** [{paper.title}]({paper.abs_url})\n"
                f"*{paper.primary_category}*\n\n"
                f"_LLM 分析失败_: `{err_safe}`\n\n"
                f"摘要摘录: {_escape_md(paper.abstract[:400])}…"
            )
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": body}})
        elements.append({"tag": "hr"})
    return {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": elements,
    }


async def send_feishu_card(webhook_url: str, card: dict[str, Any], *, timeout: float = 30.0) -> bool:
    payload = {"msg_type": "interactive", "card": card}
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        trust_env=True,
    ) as session:
        for attempt in range(3):
            try:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status != 200:
                        logger.warning("飞书 HTTP %s", resp.status)
                        await asyncio.sleep(2**attempt)
                        continue
                    data = await resp.json()
                    if data.get("code") == 0:
                        return True
                    logger.warning("飞书业务错误: %s", data)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning("飞书发送异常: %s", e)
            await asyncio.sleep(2**attempt)
    return False
