"""Shared pytest configuration."""


def pytest_configure(config):
    # Starlette's TestClient now prefers the `httpx2` package and warns when it falls
    # back to `httpx`. Behaviour is unchanged. The durable fix is to replace the dev
    # dependency `httpx` with `httpx2` in pyproject.toml (coordinator-owned); until
    # then, silence only this exact message.
    config.addinivalue_line(
        "filterwarnings",
        "ignore:Using `httpx` with `starlette.testclient` is deprecated",
    )
