# Scripts package for VPS configuration

from __future__ import annotations

import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "vps.yml"


def find_project_root() -> Path:
    """Find the project root directory.

    1. Walk up from CWD (works when inside the project)
    2. Fall back to saved path in ~/.config/vps.yml (works from anywhere)
    """
    # Walk up from CWD
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "ansible").is_dir():
            _save_project_root(parent)
            return parent

    # Fall back to saved config
    if CONFIG_PATH.exists():
        import yaml

        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        saved = cfg.get("project_root")
        if saved:
            p = Path(saved)
            if (p / "pyproject.toml").exists():
                return p

    print("Error: could not find project root", file=sys.stderr)
    print(f"Run 'vps' from the project directory once, or set project_root in {CONFIG_PATH}", file=sys.stderr)
    sys.exit(1)


def _save_project_root(root: Path) -> None:
    """Auto-save project root to config for global access."""
    import yaml

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            existing = yaml.safe_load(f) or {}

    if existing.get("project_root") == str(root):
        return

    existing["project_root"] = str(root)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(existing, f, default_flow_style=False)
