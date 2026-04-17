"""arXiv 官方 HTML 全文抓取与轻量结构化。"""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

import aiohttp
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _extract_version_from_entry_id(entry_id: str) -> str:
    match = re.search(r"v(\d+)$", entry_id.strip())
    if not match:
        raise ValueError(f"无法从 entry.id 提取版本号: {entry_id}")
    return f"v{match.group(1)}"


async def _fetch_atom_entry(
    session: aiohttp.ClientSession,
    paper_id: str,
    timeout: float,
) -> ET.Element:
    query_url = f"{ARXIV_API_URL}?id_list={paper_id}"
    async with session.get(query_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        if resp.status != 200:
            raise RuntimeError(f"arXiv API 请求失败: HTTP {resp.status}")
        xml = await resp.text()
    root = ET.fromstring(xml)
    entry = root.find("atom:entry", ARXIV_NS)
    if entry is None:
        raise RuntimeError(f"arXiv API 未返回 entry: {paper_id}")
    return entry


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_section_key(heading: str) -> str:
    norm = _normalize_text(heading).lower()
    norm = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", norm)
    return norm


def _build_fulltext_context(root: Tag, max_chars: int) -> str:
    items: list[Tag] = []
    for el in root.descendants:
        if not isinstance(el, Tag) or not el.name:
            continue
        if re.fullmatch(r"h[2-4]", el.name) or el.name == "p":
            items.append(el)

    headings = [i for i, t in enumerate(items) if re.fullmatch(r"h[2-4]", t.name or "")]
    if not headings:
        raise RuntimeError("HTML 未解析出章节结构")

    chunks: list[str] = []
    for idx_pos, idx in enumerate(headings):
        h = items[idx]
        heading = _normalize_text(h.get_text(" ", strip=True))
        if not heading:
            continue

        end = len(items)
        level = int((h.name or "h2")[1])
        for next_idx in headings[idx_pos + 1 :]:
            nxt = items[next_idx]
            nxt_level = int((nxt.name or "h2")[1])
            if nxt_level <= level:
                end = next_idx
                break

        paragraphs: list[str] = []
        for node in items[idx + 1 : end]:
            if node.name == "p":
                p = _normalize_text(node.get_text(" ", strip=True))
                if p:
                    paragraphs.append(p)

        if not paragraphs:
            continue

        section_key = _extract_section_key(heading)
        chunk = [f"## {heading}", f"[section_key={section_key}]"]
        chunk.extend(paragraphs[:4])
        chunks.append("\n".join(chunk))

    context = "\n\n".join(chunks).strip()
    if not context:
        raise RuntimeError("HTML 章节无可用正文")
    if len(context) > max_chars:
        return context[:max_chars] + "\n\n...(全文上下文已截断)"
    return context


async def fetch_arxiv_html_context(
    paper_id: str,
    *,
    timeout: float = 40.0,
    max_chars: int = 16000,
) -> tuple[str, str]:
    """
    获取 arXiv 官方 HTML 全文上下文。

    Returns:
        (html_url, fulltext_context)
    """
    paper_id = paper_id.strip()
    if not paper_id:
        raise ValueError("paper_id 不能为空")

    headers = {"User-Agent": "arxiv-daily-feishu/1.0 (html fulltext)"}
    async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
        entry = await _fetch_atom_entry(session, paper_id, timeout)
        entry_id = entry.find("atom:id", ARXIV_NS)
        if entry_id is None or not entry_id.text:
            raise RuntimeError(f"arXiv entry.id 缺失: {paper_id}")
        version = _extract_version_from_entry_id(entry_id.text)

        html_url = f"https://arxiv.org/html/{paper_id}{version}"
        async with session.get(html_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"arXiv HTML 不可访问: HTTP {resp.status}")
            html = await resp.text()

    if not html or len(html) < 1000:
        raise RuntimeError("arXiv HTML 为空或过短")

    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    root = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", id="content")
        or soup.body
        or soup
    )
    if not isinstance(root, Tag):
        raise RuntimeError("HTML 内容根节点无效")

    context = _build_fulltext_context(root, max_chars=max_chars)
    return html_url, context


async def fetch_arxiv_html_debug(
    paper_id: str,
    *,
    timeout: float = 40.0,
    max_chars: int = 16000,
) -> tuple[str, str, str]:
    """
    调试用：返回 (html_url, raw_html, cleaned_context)。
    """
    paper_id = paper_id.strip()
    if not paper_id:
        raise ValueError("paper_id 不能为空")

    headers = {"User-Agent": "arxiv-daily-feishu/1.0 (html debug)"}
    async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
        entry = await _fetch_atom_entry(session, paper_id, timeout)
        entry_id = entry.find("atom:id", ARXIV_NS)
        if entry_id is None or not entry_id.text:
            raise RuntimeError(f"arXiv entry.id 缺失: {paper_id}")
        version = _extract_version_from_entry_id(entry_id.text)

        html_url = f"https://arxiv.org/html/{paper_id}{version}"
        async with session.get(html_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"arXiv HTML 不可访问: HTTP {resp.status}")
            raw_html = await resp.text()

    if not raw_html or len(raw_html) < 1000:
        raise RuntimeError("arXiv HTML 为空或过短")

    soup = BeautifulSoup(raw_html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    root = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", id="content")
        or soup.body
        or soup
    )
    if not isinstance(root, Tag):
        raise RuntimeError("HTML 内容根节点无效")

    cleaned_context = _build_fulltext_context(root, max_chars=max_chars)
    return html_url, raw_html, cleaned_context
