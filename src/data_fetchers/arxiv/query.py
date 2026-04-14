"""arXiv API 查询 URL 构建（与 ai-insight-tracker 同源思路）。"""

from urllib.parse import urlencode

ARXIV_API_ENDPOINT = "http://export.arxiv.org/api/query"


def build_single_category_query(
    category: str,
    max_results: int = 100,
    start: int = 0,
    sort_by: str = "lastUpdatedDate",
    sort_order: str = "descending",
) -> str:
    params = {
        "search_query": f"cat:{category}",
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    return f"{ARXIV_API_ENDPOINT}?{urlencode(params)}"


def build_id_query(paper_ids: list[str]) -> str:
    id_list = ",".join(paper_ids)
    return f"{ARXIV_API_ENDPOINT}?{urlencode({'id_list': id_list})}"
