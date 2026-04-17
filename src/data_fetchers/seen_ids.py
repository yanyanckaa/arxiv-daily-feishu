"""已推送论文 ID 持久化（职责类似参考项目中的 ids_tracker / fetched 记录）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_seen_id_list(path: Path) -> list[str]:
    """按文件顺序读取 seen ids（新 -> 旧）。"""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            out: list[str] = []
            seen: set[str] = set()
            for x in data:
                sid = str(x)
                if sid not in seen:
                    seen.add(sid)
                    out.append(sid)
            return out
        if isinstance(data, dict) and "ids" in data:
            out = []
            seen = set()
            for x in data["ids"]:
                sid = str(x)
                if sid not in seen:
                    seen.add(sid)
                    out.append(sid)
            return out
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取 seen_ids 失败 %s: %s", path, e)
    return []


def load_seen_ids(path: Path) -> set[str]:
    return set(load_seen_id_list(path))


def append_seen_ids(path: Path, ids: list[str], *, max_keep: int = 8000) -> None:
    if not ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_seen_id_list(path)
    merged: list[str] = []
    seen: set[str] = set()
    for i in ids + current:
        if i not in seen:
            seen.add(i)
            merged.append(i)
    merged = merged[:max_keep]
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
