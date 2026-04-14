#!/usr/bin/env python3
"""
每日入口：arXiv → LLM → 飞书

用法（在项目根目录 arxiv-daily-feishu 下）:
    python scripts/daily_arxiv.py

环境变量见仓库根目录 .env.example
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config.proxy import apply_proxy_env  # noqa: E402
from src.pipeline.daily import run_daily  # noqa: E402


def main() -> None:
    apply_proxy_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="arXiv 每日简报 → 飞书")
    parser.parse_args()
    code = asyncio.run(run_daily())
    sys.exit(code)


if __name__ == "__main__":
    main()
