#!/usr/bin/env python3
"""中间测试：抓取 arXiv 官方 HTML，并落盘原文与清洗结果。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import Settings
from src.data_fetchers.arxiv import ArxivClient, fetch_arxiv_html_debug


def _pick_candidate_ids(args_paper_id: str | None, settings: Settings) -> list[str]:
    if args_paper_id:
        return [args_paper_id.strip()]
    client = ArxivClient(
        delay_between_requests=settings.arxiv_request_delay,
        timeout=settings.arxiv_http_timeout,
    )
    papers = asyncio.run(client.fetch_recent(settings.arxiv_categories, hours=settings.arxiv_hours))
    if not papers:
        raise RuntimeError("未抓到可测试论文，请手动传 --paper-id")
    return [p.id for p in papers[:10]]


def main() -> None:
    parser = argparse.ArgumentParser(description="测试 arXiv HTML 抓取与清洗")
    parser.add_argument("--paper-id", type=str, default="", help="指定 arXiv ID（如 2604.15272）")
    parser.add_argument("--max-chars", type=int, default=16000, help="清洗后上下文最大字符数")
    args = parser.parse_args()

    settings = Settings.load()
    paper_id = ""
    html_url = ""
    raw_html = ""
    cleaned_context = ""
    errors: list[str] = []
    for candidate_id in _pick_candidate_ids(args.paper_id or None, settings):
        try:
            html_url, raw_html, cleaned_context = asyncio.run(
                fetch_arxiv_html_debug(
                    candidate_id,
                    timeout=settings.arxiv_html_fetch_timeout,
                    max_chars=max(2000, args.max_chars),
                )
            )
            paper_id = candidate_id
            break
        except Exception as e:
            errors.append(f"{candidate_id}: {e}")

    if not paper_id:
        raise RuntimeError(
            "候选论文均未抓到可用 HTML。\n" + "\n".join(errors)
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("data") / "debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"html_fetch_{paper_id}_{ts}.raw.html"
    cleaned_path = out_dir / f"html_fetch_{paper_id}_{ts}.cleaned.md"

    raw_path.write_text(raw_html, encoding="utf-8")
    cleaned_path.write_text(cleaned_context, encoding="utf-8")

    print("HTML 抓取测试完成")
    print(f"- paper_id: {paper_id}")
    print(f"- html_url: {html_url}")
    print(f"- raw_html_chars: {len(raw_html)}")
    print(f"- cleaned_chars: {len(cleaned_context)}")
    print(f"- raw_html_file: {raw_path}")
    print(f"- cleaned_file: {cleaned_path}")


if __name__ == "__main__":
    main()
