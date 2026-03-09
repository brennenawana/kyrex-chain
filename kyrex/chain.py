"""Chain state read/write for kyrex.json and history/blocks.jsonl."""

import json
from pathlib import Path


def load_state(repo_root: Path) -> dict:
    """Load kyrex.json chain state."""
    with open(repo_root / "kyrex.json") as f:
        return json.load(f)


def save_state(repo_root: Path, state: dict) -> None:
    """Write kyrex.json chain state."""
    with open(repo_root / "kyrex.json", "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def load_blocks(repo_root: Path) -> list[dict]:
    """Load all blocks from history/blocks.jsonl."""
    path = repo_root / "history" / "blocks.jsonl"
    if not path.exists():
        return []
    blocks = []
    for line in path.read_text().strip().splitlines():
        if line.strip():
            blocks.append(json.loads(line))
    return blocks


def append_block(repo_root: Path, block: dict) -> None:
    """Append a block to history/blocks.jsonl."""
    path = repo_root / "history" / "blocks.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(block) + "\n")


def calculate_reward(block_height: int, improvement_pct: float) -> float:
    """Calculate KRX reward for a block."""
    halvings = block_height // 210_000
    base = 50.0 / (2 ** halvings)

    if improvement_pct >= 5.0:
        multiplier = 5.0
    elif improvement_pct >= 1.0:
        multiplier = 2.0
    else:
        multiplier = 1.0

    return round(base * multiplier, 8)
