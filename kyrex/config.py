"""Miner configuration management (~/.kyrex/config.toml)."""

import os
import tomllib
from pathlib import Path

CONFIG_DIR = Path.home() / ".kyrex"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_config() -> dict | None:
    """Load miner config. Returns None if not initialized."""
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def save_config(config: dict) -> None:
    """Save miner config as TOML."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for section, values in config.items():
        lines.append(f"[{section}]")
        for key, val in values.items():
            if isinstance(val, str):
                lines.append(f'{key} = "{val}"')
            else:
                lines.append(f"{key} = {val}")
        lines.append("")
    CONFIG_FILE.write_text("\n".join(lines))


def get_miner_id(config: dict) -> str:
    """Return miner_id from config."""
    return config["miner"]["id"]


def find_repo_root() -> Path | None:
    """Walk up from cwd to find a directory containing kyrex.json."""
    p = Path.cwd()
    while p != p.parent:
        if (p / "kyrex.json").exists():
            return p
        p = p.parent
    return None
