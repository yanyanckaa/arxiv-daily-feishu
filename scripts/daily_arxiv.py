#!/usr/bin/env python3
"""
每日入口：arXiv → LLM → 飞书

用法（在项目根目录 arxiv-daily-feishu 下）:
    python scripts/daily_arxiv.py

环境变量见仓库根目录 .env.example
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.__main__ import run_cli  # noqa: E402


def main() -> None:
    # 兼容旧脚本入口，避免与 `python -m src` 逻辑漂移。
    parser = argparse.ArgumentParser(description="arXiv 每日简报 → 飞书")
    parser.parse_args()
    code = run_cli()
    sys.exit(code)


if __name__ == "__main__":
    main()
