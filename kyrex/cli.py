"""Kyrex CLI — entry point for all commands."""

import subprocess
import sys

import click
from rich.console import Console

from kyrex.config import load_config, save_config, find_repo_root, get_miner_id
from kyrex.chain import load_state, load_blocks
from kyrex.display import show_status, show_log, show_leaderboard

console = Console()


def require_repo():
    """Find repo root or exit with error."""
    root = find_repo_root()
    if root is None:
        console.print("[red]Error:[/] Not inside a Kyrex chain repo (no kyrex.json found).")
        console.print("Run this command from inside a cloned kyrex-chain directory.")
        raise SystemExit(1)
    return root


@click.group()
@click.version_option(package_name="kyrex-chain")
def main():
    """Kyrex — Decentralized ML Research Mining CLI."""
    pass


@main.command()
@click.option("--name", required=True, help="Your display name (e.g. 'brennen')")
@click.option("--gpu", required=True, help="Your GPU type (e.g. 'H100', 'RTX 4090')")
@click.option("--agent-provider", default="claude", help="AI agent provider (claude/openai/local)")
@click.option("--agent-model", default="claude-sonnet-4-6", help="AI model to use")
def init(name: str, gpu: str, agent_provider: str, agent_model: str):
    """Initialize a new miner identity."""
    root = require_repo()
    state = load_state(root)

    miner_id = f"{name}@{gpu}"

    config = {
        "miner": {
            "id": miner_id,
            "name": name,
            "gpu": gpu,
        },
        "agent": {
            "provider": agent_provider,
            "model": agent_model,
        },
        "repo": {
            "remote": "origin",
            "branch": "main",
        },
    }

    save_config(config)

    console.print()
    console.print(f"[bold green]✓[/] Miner initialized: [bold]{miner_id}[/]")
    console.print(f"  Config saved to ~/.kyrex/config.toml")
    console.print()

    # Check if data is prepared
    from pathlib import Path
    cache_dir = Path.home() / ".cache" / "kyrex"
    if not (cache_dir / "data").exists() or not (cache_dir / "tokenizer").exists():
        console.print("[yellow]Data not found.[/] Run: [bold]uv run prepare.py[/]")
    else:
        console.print("[dim]Data ready at ~/.cache/kyrex/[/]")

    console.print()
    show_status(state, config)


@main.command()
def status():
    """Show current chain state and miner info."""
    root = require_repo()
    state = load_state(root)
    config = load_config()
    show_status(state, config)


@main.command()
@click.option("--all", "show_all", is_flag=True, help="Show all blocks")
@click.option("--miner", "miner_filter", default=None, help="Filter by miner ID")
@click.option("-n", "limit", default=10, help="Number of blocks to show")
def log(show_all: bool, miner_filter: str, limit: int):
    """Show block history."""
    root = require_repo()
    blocks = load_blocks(root)
    if show_all:
        limit = len(blocks)
    show_log(blocks, limit=limit, miner_filter=miner_filter)


@main.command()
def leaderboard():
    """Show token leaderboard."""
    root = require_repo()
    state = load_state(root)
    show_leaderboard(state)


@main.command()
@click.option("--rounds", default=0, help="Number of rounds (0 = infinite)")
@click.option("--dry-run", is_flag=True, help="Run one experiment without committing or pushing")
@click.option("--manual", is_flag=True, help="Edit train.py manually instead of using AI agent")
def mine(rounds: int, dry_run: bool, manual: bool):
    """Start the mining loop."""
    root = require_repo()
    config = load_config()
    if config is None:
        console.print("[red]Error:[/] Not initialized. Run: [bold]kyrex init --name YOUR_NAME --gpu YOUR_GPU[/]")
        raise SystemExit(1)

    from kyrex.mine import mine_round

    miner_id = get_miner_id(config)
    console.print(f"\n[bold cyan]⛏  Kyrex Miner: {miner_id}[/]")

    if dry_run:
        console.print("[dim]Dry run mode — will not commit or push.[/]")
        mine_round(root, config, dry_run=True, manual=manual)
        return

    round_num = 0
    blocks_mined = 0

    try:
        while True:
            round_num += 1
            if rounds > 0:
                console.print(f"\n[bold]Round {round_num}/{rounds}[/]")
            else:
                console.print(f"\n[bold]Round {round_num}[/]")

            success = mine_round(root, config, dry_run=False, manual=manual)
            if success:
                blocks_mined += 1

            if rounds > 0 and round_num >= rounds:
                break

    except KeyboardInterrupt:
        console.print(f"\n\n[bold]Mining stopped.[/] Blocks mined this session: {blocks_mined}")


if __name__ == "__main__":
    main()
