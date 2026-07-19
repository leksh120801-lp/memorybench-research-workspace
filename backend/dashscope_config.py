"""Shared DashScope SDK configuration. Imported lazily (only when a caller
actually needs to make a call) so `dashscope` isn't a hard requirement for
running in offline mode.

Endpoint: this project's DashScope account is international
(home.qwencloud.com), not mainland, so the default base URL is the
international endpoint. Override with DASHSCOPE_BASE_URL if you're on a
mainland account (https://dashscope.aliyuncs.com/api/v1).
"""

from __future__ import annotations

import os

DEFAULT_BASE_URL_INTL = "https://dashscope-intl.aliyuncs.com/api/v1"


def configure_dashscope(api_key: str | None = None):
    """Sets dashscope.api_key and dashscope.base_http_api_url from env (or
    the given api_key override) and returns the configured module."""
    import dashscope

    dashscope.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
    dashscope.base_http_api_url = os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL_INTL)
    return dashscope
