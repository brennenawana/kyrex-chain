"""The mining loop — the heart of Kyrex."""

import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from kyrex.chain import load_state, save_state, load_blocks, append_block, calculate_reward
from kyrex.config import get_miner_id

console = Console()

TRAIN_TIMEOUT = 330  # 5 min + 30s buffer


def git_run(args: list[str], repo_root: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the repo."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=check,
    )


def sync_chain(repo_root: Path, remote: str, branch: str) -> bool:
    """Pull latest chain tip. Returns True if successful."""
    console.print("[dim]  Syncing chain...[/]")
    result = git_run(["pull", "--ff-only", remote, branch], repo_root, check=False)
    if result.returncode == 0:
        console.print("[dim]  Chain synced.[/]")
        return True

    # Pull failed — probably diverged. Reset to remote.
    console.print("[yellow]  Pull failed, resetting to remote...[/]")
    git_run(["fetch", remote], repo_root, check=False)
    git_run(["reset", "--hard", f"{remote}/{branch}"], repo_root, check=False)
    return True


def run_training(repo_root: Path) -> tuple[float | None, dict]:
    """Run uv run train.py and parse results. Returns (val_bpb, metadata) or (None, {})."""
    console.print("[bold]  Training for 5 minutes...[/]")
    t0 = time.time()

    try:
        result = subprocess.run(
            ["uv", "run", "train.py"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=TRAIN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        console.print("[red]  Training timed out![/]")
        return None, {}

    elapsed = time.time() - t0

    if result.returncode != 0:
        console.print(f"[red]  Training crashed (exit {result.returncode})[/]")
        # Show last few lines of stderr for debugging
        stderr_lines = result.stderr.strip().splitlines()
        for line in stderr_lines[-5:]:
            console.print(f"[dim]  {line}[/]")
        return None, {}

    # Parse val_bpb from output
    output = result.stdout + result.stderr
    val_bpb = _parse_metric(output, "val_bpb")
    if val_bpb is None:
        console.print("[red]  Could not parse val_bpb from output![/]")
        return None, {}

    metadata = {
        "training_duration_sec": round(elapsed, 1),
        "peak_vram_mb": _parse_metric(output, "peak_vram_mb") or 0,
        "mfu_percent": _parse_metric(output, "mfu_percent") or 0,
        "total_tokens_M": _parse_metric(output, "total_tokens_M") or 0,
        "num_steps": int(_parse_metric(output, "num_steps") or 0),
        "depth": int(_parse_metric(output, "depth") or 0),
    }

    console.print(f"[bold green]  val_bpb: {val_bpb:.6f}[/] (in {elapsed:.0f}s)")
    return val_bpb, metadata


def _parse_metric(output: str, name: str) -> float | None:
    """Parse a metric like 'val_bpb: 0.997900' from training output."""
    pattern = rf"^{re.escape(name)}:\s+([\d.]+)"
    for line in output.splitlines():
        m = re.match(pattern, line.strip())
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def build_block(
    state: dict,
    miner_id: str,
    new_bpb: float,
    description: str,
    metadata: dict,
    commit_hash: str = "pending",
) -> dict:
    """Build a new block dict and update chain state in place."""
    chain = state["chain"]
    current_bpb = chain["current_val_bpb"]
    initial_bpb = chain["initial_val_bpb"]
    new_height = chain["height"] + 1
    improvement = current_bpb - new_bpb
    improvement_pct = (improvement / current_bpb) * 100

    reward = calculate_reward(new_height, improvement_pct)

    # Update chain state
    chain["height"] = new_height
    chain["current_val_bpb"] = round(new_bpb, 6)
    chain["total_improvement_pct"] = round((1 - new_bpb / initial_bpb) * 100, 2)
    # tip_hash updated after commit

    gpu_type = miner_id.split("@")[-1] if "@" in miner_id else "unknown"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Update last_block
    state["last_block"] = {
        "height": new_height,
        "commit_hash": commit_hash,
        "parent_hash": chain["tip_hash"],
        "miner_id": miner_id,
        "val_bpb_before": round(current_bpb, 6),
        "val_bpb_after": round(new_bpb, 6),
        "improvement": round(improvement, 6),
        "improvement_pct": round(improvement_pct, 2),
        "experiment_description": description,
        "gpu_type": gpu_type,
        "agent_model": "claude-sonnet-4-6",
        "training_duration_sec": metadata.get("training_duration_sec", 0),
        "peak_vram_mb": metadata.get("peak_vram_mb", 0),
        "timestamp": now,
    }

    # Update ledger
    ledger = state["ledger"]
    if miner_id not in ledger:
        ledger[miner_id] = {
            "balance": 0.0,
            "blocks_mined": 0,
            "total_earned": 0.0,
            "first_block": new_height,
            "last_block": new_height,
        }
    ledger[miner_id]["balance"] = round(ledger[miner_id]["balance"] + reward, 8)
    ledger[miner_id]["total_earned"] = round(ledger[miner_id]["total_earned"] + reward, 8)
    ledger[miner_id]["blocks_mined"] += 1
    ledger[miner_id]["last_block"] = new_height

    # Update token
    state["token"]["total_emitted"] = round(state["token"]["total_emitted"] + reward, 8)

    # Build block entry for blocks.jsonl
    block_entry = {
        "height": new_height,
        "commit": commit_hash[:7] if len(commit_hash) > 7 else commit_hash,
        "parent": chain["tip_hash"][:7] if len(chain["tip_hash"]) > 7 else chain["tip_hash"],
        "miner": miner_id,
        "val_bpb_before": round(current_bpb, 6),
        "val_bpb_after": round(new_bpb, 6),
        "improvement": round(improvement, 6),
        "desc": description,
        "gpu": gpu_type,
        "agent": "claude-sonnet-4-6",
        "reward": reward,
        "timestamp": now,
    }

    return block_entry


def commit_block(
    repo_root: Path,
    state: dict,
    block_entry: dict,
    miner_id: str,
) -> str | None:
    """Stage files, commit, return commit hash. Returns None on failure."""
    height = state["chain"]["height"]
    before = block_entry["val_bpb_before"]
    after = block_entry["val_bpb_after"]
    imp = block_entry["improvement"]

    # Write updated state
    save_state(repo_root, state)
    append_block(repo_root, block_entry)

    # Stage
    git_run(["add", "train.py", "kyrex.json", "history/blocks.jsonl"], repo_root)

    # Commit
    msg = f"Block #{height}: val_bpb {before:.4f} → {after:.4f} (Δ={-imp:+.4f}) by {miner_id}"
    result = git_run(["commit", "-m", msg], repo_root, check=False)
    if result.returncode != 0:
        console.print(f"[red]  Commit failed: {result.stderr[:200]}[/]")
        return None

    # Get commit hash
    hash_result = git_run(["rev-parse", "HEAD"], repo_root)
    commit_hash = hash_result.stdout.strip()

    # Update tip_hash and commit_hash in state with real values
    state["chain"]["tip_hash"] = commit_hash
    state["last_block"]["commit_hash"] = commit_hash
    block_entry["commit"] = commit_hash[:7]

    # Re-save with real hashes
    save_state(repo_root, state)
    # Amend the commit to include updated hashes
    git_run(["add", "kyrex.json"], repo_root)
    git_run(["commit", "--amend", "--no-edit"], repo_root, check=False)

    final_hash = git_run(["rev-parse", "HEAD"], repo_root).stdout.strip()
    state["chain"]["tip_hash"] = final_hash
    state["last_block"]["commit_hash"] = final_hash

    return final_hash


def push_block(repo_root: Path, remote: str, branch: str) -> bool:
    """Push to remote. Returns True on success, False if rejected (race lost)."""
    result = git_run(["push", remote, branch], repo_root, check=False)
    return result.returncode == 0


def handle_race_loss(repo_root: Path, remote: str, branch: str) -> None:
    """Handle a rejected push — discard our block and sync to remote tip."""
    console.print("[yellow]  Push rejected — someone else mined first.[/]")
    console.print("[dim]  Discarding block and syncing...[/]")

    # Undo our commit(s)
    git_run(["reset", "--hard", f"{remote}/{branch}"], repo_root, check=False)
    git_run(["pull", "--ff-only", remote, branch], repo_root, check=False)

    console.print("[dim]  Starting fresh from new chain tip.[/]")


def mine_round(
    repo_root: Path,
    config: dict,
    dry_run: bool = False,
    manual: bool = False,
) -> bool:
    """Run one mining round. Returns True if a block was mined."""
    from kyrex.agent import mutate

    miner_id = get_miner_id(config)
    remote = config["repo"]["remote"]
    branch = config["repo"]["branch"]
    provider = "manual" if manual else config["agent"]["provider"]

    # 1. Sync
    if not dry_run:
        sync_chain(repo_root, remote, branch)

    state = load_state(repo_root)
    current_bpb = state["chain"]["current_val_bpb"]
    height = state["chain"]["height"]
    min_improvement = state["config"]["min_improvement"]

    console.print(f"\n[bold cyan]═══ Round at block #{height}, val_bpb: {current_bpb:.4f} ═══[/]")

    # 2. Backup train.py
    train_py = repo_root / "train.py"
    backup = train_py.read_text()

    # 3. Mutate
    recent_blocks = load_blocks(repo_root)
    description = mutate(repo_root, provider=provider, recent_blocks=recent_blocks)
    if description is None:
        console.print("[dim]  No mutation produced, restoring backup.[/]")
        train_py.write_text(backup)
        return False

    console.print(f"[dim]  Mutation: \"{description}\"[/]")

    # Check train.py actually changed
    if train_py.read_text() == backup:
        console.print("[dim]  train.py unchanged after mutation, skipping.[/]")
        return False

    # 4. Train
    new_bpb, metadata = run_training(repo_root)
    if new_bpb is None:
        console.print("[yellow]  Experiment failed, restoring backup.[/]")
        train_py.write_text(backup)
        git_run(["checkout", "train.py"], repo_root, check=False)
        return False

    # 5. Evaluate
    improvement = current_bpb - new_bpb
    if improvement < min_improvement:
        console.print(f"[yellow]  No improvement: {new_bpb:.4f} >= {current_bpb:.4f} (Δ={-improvement:+.4f})[/]")
        train_py.write_text(backup)
        git_run(["checkout", "train.py"], repo_root, check=False)
        return False

    improvement_pct = (improvement / current_bpb) * 100
    reward = calculate_reward(height + 1, improvement_pct)
    console.print(f"[bold green]  Improvement found! {current_bpb:.4f} → {new_bpb:.4f} (Δ={-improvement:+.4f}, {improvement_pct:.2f}%)[/]")
    console.print(f"[bold yellow]  Reward: {reward:.2f} KRX[/]")

    if dry_run:
        console.print("[cyan]  --dry-run: skipping commit and push.[/]")
        train_py.write_text(backup)
        git_run(["checkout", "train.py"], repo_root, check=False)
        return True

    # 6. Commit
    block_entry = build_block(state, miner_id, new_bpb, description, metadata)
    commit_hash = commit_block(repo_root, state, block_entry, miner_id)
    if commit_hash is None:
        train_py.write_text(backup)
        return False

    console.print(f"[dim]  Committed: {commit_hash[:7]}[/]")

    # 7. Push
    if push_block(repo_root, remote, branch):
        console.print(f"[bold green]  ✓ Block #{state['chain']['height']} mined! Reward: {reward:.2f} KRX[/]")
        return True
    else:
        handle_race_loss(repo_root, remote, branch)
        return False
