from __future__ import annotations

from pathlib import Path
import sys

# Editable installs in this repo currently add `<repo>/src` to sys.path.
# Ensure the repository root is also present so `src.sync_commands` resolves.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

def cli() -> int:
    from src.sync_commands import cli as sync_cli

    return sync_cli()

