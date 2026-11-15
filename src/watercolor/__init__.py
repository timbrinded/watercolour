"""Watercolor painting simulator and harness."""

ENGINE_VERSION = "0.6.1"


def main() -> None:
    from .cli import main as run

    run()
