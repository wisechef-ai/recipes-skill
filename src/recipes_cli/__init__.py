"""recipes_cli — pip-installable wrapper around the canonical bin/recipes script.

The wheel bundles bin/recipes as recipes_cli/_main.py (see pyproject.toml
force-include). Installing the package exposes a `recipes` console script
that runs that bundled module.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

__all__ = ["main"]


def main() -> None:
    """Entry point for the `recipes` console script."""
    bundled = Path(__file__).parent / "_main.py"
    if not bundled.exists():
        sys.stderr.write(
            f"recipes_cli: bundled CLI not found at {bundled}. "
            "Reinstall: pip install --force-reinstall wisechef-recipes\n"
        )
        sys.exit(127)
    runpy.run_path(str(bundled), run_name="__main__")
