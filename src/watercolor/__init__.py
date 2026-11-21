"""Watercolor painting simulator and harness."""

ENGINE_VERSION = "0.12.0"


def main() -> None:
    from .cli import main as run

    run()
