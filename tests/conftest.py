"""The option that admits the calibration gates to a test run.

The global gates of the calibration suite repaint their scenarios, which takes minutes on a graphics card, so the
tests marked calibration are skipped unless the run asks for them with --calibration. An option is used rather than
a default marker expression, which any -m given on the command line would replace.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--calibration",
        action="store_true",
        help="also run the global gates of the calibration suite, which repaint their scenarios (minutes on a GPU)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--calibration"):
        return
    skip = pytest.mark.skip(reason="the calibration gates run only with --calibration")
    for item in items:
        if "calibration" in item.keywords:
            item.add_marker(skip)
