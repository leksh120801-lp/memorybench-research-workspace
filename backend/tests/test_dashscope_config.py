"""dashscope_config.py is pure configuration plumbing — verified without any
real network call by checking the module-level attributes it sets."""

from backend.dashscope_config import DEFAULT_BASE_URL_INTL, configure_dashscope


def test_defaults_to_international_endpoint(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)
    ds = configure_dashscope("k")
    assert ds.base_http_api_url == DEFAULT_BASE_URL_INTL == "https://dashscope-intl.aliyuncs.com/api/v1"


def test_base_url_overridable_for_mainland_accounts(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    ds = configure_dashscope("k")
    assert ds.base_http_api_url == "https://dashscope.aliyuncs.com/api/v1"


def test_reads_api_key_from_dashscope_api_key_env_var(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "from-env")
    ds = configure_dashscope()
    assert ds.api_key == "from-env"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "from-env")
    ds = configure_dashscope("explicit-key")
    assert ds.api_key == "explicit-key"
