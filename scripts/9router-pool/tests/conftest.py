"""Pytest config for 9router-pool tests."""


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests (needs tor + 9router up)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: tests needing live docker infra"
    )
