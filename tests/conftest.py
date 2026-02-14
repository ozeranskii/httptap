import pytest
from faker import Faker


@pytest.fixture(autouse=True)
def clear_proxy_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear proxy environment variables for all tests to ensure consistent behavior."""
    proxy_vars = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ]
    for var in proxy_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def faker() -> Faker:
    return Faker()
