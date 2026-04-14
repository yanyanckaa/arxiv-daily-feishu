"""异步拉取 arXiv 最近更新（按分类、分页、限流）。"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import feedparser
from dateutil import parser as date_parser

from src.data_fetchers.arxiv.query import build_single_category_query
from src.models.paper import Paper

logger = logging.getLogger(__name__)


class ArxivClient:
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        page_size: int = 100,
        max_pages: int = 15,
        delay_between_requests: float = 3.0,
        max_retries: int = 3,
    ):
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._page_size = page_size
        self._max_pages = max(1, max_pages)
        self._delay = delay_between_requests
        self._max_retries = max_retries
        self._last_request_time = 0.0
        self._sem = asyncio.Semaphore(1)

    async def fetch_recent(
        self,
        categories: list[str],
        hours: int = 25,
    ) -> list[Paper]:
        tasks = [self._rate_limited_fetch_category(cat, hours=hours) for cat in categories]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_papers: list[Paper] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                # TimeoutError 等 str() 可能为空，用类型+repr 便于排查
                logger.warning("分类 %s 获取失败: %s: %r", categories[i], type(r).__name__, r)
            else:
                all_papers.extend(r)

        seen: set[str] = set()
        unique: list[Paper] = []
        for p in all_papers:
            if p.id not in seen:
                seen.add(p.id)
                unique.append(p)

        targets = set(categories)
        # 仅用 primary 会漏掉跨类论文：cat:cs.AI 返回的条目主类可能是 cs.LG 等
        filtered = [
            p
            for p in unique
            if targets.intersection(p.categories) or p.primary_category in targets
        ]
        filtered = self._filter_by_hours(filtered, hours)
        logger.info(
            "arXiv: 原始 %d 去重 %d 主分类+时间窗 %d",
            len(all_papers),
            len(unique),
            len(filtered),
        )
        return filtered

    async def _rate_limited_fetch_category(self, category: str, hours: int) -> list[Paper]:
        async with self._sem:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            out = await self._fetch_category_paginated(category, hours=hours)
            self._last_request_time = time.time()
            return out

    def _latest_time(self, paper: Paper) -> datetime:
        pub = paper.published
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        upd = paper.updated
        if upd:
            if upd.tzinfo is None:
                upd = upd.replace(tzinfo=timezone.utc)
            return max(pub, upd)
        return pub

    async def _fetch_category_paginated(self, category: str, hours: int) -> list[Paper]:
        collected: list[Paper] = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        start = 0
        for _ in range(self._max_pages):
            url = build_single_category_query(
                category=category,
                max_results=self._page_size,
                start=start,
            )
            page = await self._fetch_and_parse(url)
            if not page:
                break
            collected.extend(page)
            if len(page) < self._page_size:
                break
            try:
                oldest = self._latest_time(page[-1])
                if oldest < cutoff:
                    break
            except Exception:
                pass
            start += self._page_size
        return collected

    async def _fetch_and_parse(self, url: str) -> list[Paper]:
        last_err: Exception | None = None
        headers = {"User-Agent": "arxiv-daily-feishu/1.0 (arxiv crawl; contact: local)"}
        for attempt in range(self._max_retries):
            try:
                async with aiohttp.ClientSession(
                    timeout=self._timeout,
                    trust_env=True,
                ) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 429:
                            logger.warning("arXiv 429，等待 30s 重试")
                            await asyncio.sleep(30)
                            continue
                        if resp.status >= 500:
                            await asyncio.sleep(2**attempt)
                            continue
                        resp.raise_for_status()
                        text = await resp.text()
                return await asyncio.to_thread(self._parse_feed, text)
            except asyncio.TimeoutError as e:
                last_err = e
                await asyncio.sleep(2**attempt)
            except aiohttp.ClientError as e:
                last_err = e
                await asyncio.sleep(2**attempt)
        if last_err:
            raise last_err
        raise RuntimeError("arXiv 请求失败")

    def _parse_feed(self, content: str) -> list[Paper]:
        feed = feedparser.parse(content)
        papers: list[Paper] = []
        for entry in feed.entries:
            try:
                papers.append(self._entry_to_paper(entry))
            except Exception as e:
                logger.warning("解析条目失败: %s", e)
        return papers

    def _entry_to_paper(self, entry: Any) -> Paper:
        arxiv_id = self._extract_arxiv_id(entry.id)
        authors = [a.name for a in entry.get("authors", [])]
        categories = [t.term for t in entry.get("tags", [])]
        primary = getattr(entry, "arxiv_primary_category", {}) or {}
        primary_cat = primary.get("term", categories[0] if categories else "")
        published = self._parse_dt(entry.get("published", ""))
        updated = self._parse_dt(entry.get("updated", "")) if entry.get("updated") else None
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        comment = getattr(entry, "arxiv_comment", None)
        title = entry.title.replace("\n", " ").strip()
        abstract = entry.summary.replace("\n", " ").strip()
        return Paper(
            id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            categories=categories,
            primary_category=primary_cat,
            pdf_url=pdf_url,
            abs_url=abs_url,
            published=published,
            updated=updated,
            comment=comment,
        )

    @staticmethod
    def _extract_arxiv_id(entry_id: str) -> str:
        tail = entry_id.split("/")[-1]
        if "v" in tail:
            return tail.split("v")[0]
        return tail

    @staticmethod
    def _parse_dt(s: str) -> datetime:
        if not s:
            return datetime.now(timezone.utc)
        try:
            dt = date_parser.parse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return datetime.now(timezone.utc)

    def _filter_by_hours(self, papers: list[Paper], hours: int) -> list[Paper]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        out: list[Paper] = []
        for p in papers:
            t = self._latest_time(p)
            if t >= cutoff:
                out.append(p)
        return out
