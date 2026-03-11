from __future__ import annotations

from pathlib import Path

from vps_cli.errors import ConfigError

__version__ = "0.1.0"

CONFIG_PATH = Path.home() / ".config" / "vps.yml"


def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "ansible").is_dir():
            _save_project_root(parent)
            return parent

    if CONFIG_PATH.exists():
        import yaml

        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        saved = cfg.get("project_root")
        if saved:
            p = Path(saved)
            if (p / "pyproject.toml").exists():
                return p

    raise ConfigError(
        f"Could not find project root. "
        f"Run 'vps' from the project directory once, or set project_root in {CONFIG_PATH}"
    )


def _save_project_root(root: Path) -> None:
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
