"""支持: 在项目根目录执行 python -m src"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from src.config.proxy import apply_proxy_env
from src.pipeline.daily import run_daily


def main() -> None:
    apply_proxy_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="arXiv 每日简报 → 飞书")
    parser.parse_args()
    sys.exit(asyncio.run(run_daily()))


if __name__ == "__main__":
    main()
