"""已推送论文 ID 持久化（职责类似参考项目中的 ids_tracker / fetched 记录）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_seen_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
        if isinstance(data, dict) and "ids" in data:
            return set(str(x) for x in data["ids"])
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取 seen_ids 失败 %s: %s", path, e)
    return set()


def append_seen_ids(path: Path, ids: list[str], *, max_keep: int = 8000) -> None:
    if not ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    current = list(load_seen_ids(path))
    merged: list[str] = []
    seen: set[str] = set()
    for i in ids + current:
        if i not in seen:
            seen.add(i)
            merged.append(i)
    merged = merged[:max_keep]
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
