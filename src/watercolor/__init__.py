"""Watercolor painting simulator and harness."""

ENGINE_VERSION = "0.8.0"


def main() -> None:
    from .cli import main as run

    run()
