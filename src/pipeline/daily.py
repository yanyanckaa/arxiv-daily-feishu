"""每日流水线：arXiv → LLM → 飞书（对应参考项目 scripts 中串联的多步任务）。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from src.config.settings import Settings
from src.data_fetchers.arxiv.client import ArxivClient
from src.data_fetchers.seen_ids import append_seen_ids, load_seen_ids
from src.llm.paper_reader import analyze_papers_bounded
from src.models.paper import Paper, PaperBriefAnalysis
from src.notifiers.feishu import build_card, send_feishu_card

logger = logging.getLogger(__name__)

CHUNK_SIZE = int(os.environ.get("FEISHU_CHUNK_SIZE", "6"))


def _data_dir() -> Path:
    root = Path(os.environ.get("ARXIV_DAILY_ROOT", Path.cwd()))
    d = root / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def run_daily() -> int:
    settings = Settings.load()
    errs = settings.validate()
    if errs:
        for e in errs:
            logger.error("配置错误: %s", e)
        return 1

    seen_path = _data_dir() / "seen_arxiv_ids.json"
    seen = load_seen_ids(seen_path)

    arxiv = ArxivClient(
        delay_between_requests=settings.arxiv_request_delay,
        timeout=settings.arxiv_http_timeout,
    )
    papers = await arxiv.fetch_recent(settings.arxiv_categories, hours=settings.arxiv_hours)
    new_papers = [p for p in papers if p.id not in seen]
    new_papers = sorted(
        new_papers,
        key=lambda x: x.published.timestamp(),
        reverse=True,
    )[: settings.max_papers]

    today = datetime.now().strftime("%Y-%m-%d")

    if not new_papers:
        logger.info("时间窗内没有新的 arXiv 论文（相对本地 seen 列表）")
        flag = os.environ.get("SEND_ON_EMPTY", "").strip().lower()
        if flag in ("1", "true", "yes", "on"):
            card = build_card(
                title=f"arXiv 每日简报 · {today}",
                date_str=today,
                sections=[],
            )
            card["elements"].append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "_当前窗口内没有需要推送的新论文（或已全部在 seen 列表中）。_",
                    },
                }
            )
            ok = await send_feishu_card(settings.feishu_webhook_url, card)
            return 0 if ok else 2
        return 0

    analyzed = await analyze_papers_bounded(settings, new_papers)

    chunks: list[list[tuple[Paper, PaperBriefAnalysis | None, str | None]]] = []
    buf: list[tuple[Paper, PaperBriefAnalysis | None, str | None]] = []
    for item in analyzed:
        buf.append(item)
        if len(buf) >= max(1, CHUNK_SIZE):
            chunks.append(buf)
            buf = []
    if buf:
        chunks.append(buf)

    total = len(chunks)
    for idx, part in enumerate(chunks, start=1):
        title = f"arXiv 每日简报 · {today}"
        if total > 1:
            title = f"{title} ({idx}/{total})"
        card = build_card(title=title, date_str=today, sections=part)
        ok = await send_feishu_card(settings.feishu_webhook_url, card)
        if not ok:
            logger.error("飞书发送失败，批次 %d/%d，已中止后续发送", idx, total)
            return 2
        batch_ids = [t[0].id for t in part]
        append_seen_ids(seen_path, batch_ids)

    logger.info("完成: 处理 %d 篇，飞书分 %d 条卡片", len(new_papers), total)
    return 0
