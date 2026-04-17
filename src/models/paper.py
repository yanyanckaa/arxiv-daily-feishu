"""论文实体与 LLM 结构化输出（对齐参考项目的 models/paper）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Paper(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str
    categories: list[str] = Field(default_factory=list)
    primary_category: str = ""
    pdf_url: str = ""
    abs_url: str = ""
    published: datetime
    updated: Optional[datetime] = None
    comment: Optional[str] = None


class PaperBriefAnalysis(BaseModel):
    """单篇论文的轻量阅读笔记（供飞书展示）。"""

    overview: str = Field(description="一句话概括核心贡献，约 40–80 字")
    motivation: str = Field(description="研究问题，约 60–120 字")
    method: str = Field(description="方法要点，约 60–120 字")
    deep_reading: str = Field(
        default="",
        description="仔细阅读结论：基于全文章节的关键洞察，约 80–160 字",
    )
    takeaway: str = Field(description="读者可带走的一点启发或适用场景，约 40–100 字")
