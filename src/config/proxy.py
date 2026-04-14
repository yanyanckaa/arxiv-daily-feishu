"""代理：与 shell 中 export http(s)_proxy 一致，并支持只配 PROXY_URL 一处。"""

from __future__ import annotations

import os


def apply_proxy_env() -> None:
    """将 PROXY_URL 同步到常见代理环境变量（若某键已有值则不改）。

    与在命令行执行 ``export https_proxy=http://127.0.0.1:7890`` 等效；
    同时建议为走 HTTP 的 arXiv 设置 ``http_proxy``（可与 https 指向同一代理）。

    典型用法（.env 或 shell）::

        export PROXY_URL=http://127.0.0.1:7890
        # 或分别设置（优先级高于 PROXY_URL 的补全）:
        export http_proxy=http://127.0.0.1:7890
        export https_proxy=http://127.0.0.1:7890
    """
    raw = os.environ.get("PROXY_URL", "").strip()
    if not raw:
        return
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    ):
        if not os.environ.get(key):
            os.environ[key] = raw
