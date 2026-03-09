"""Terminal display helpers using Rich."""

from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def time_ago(timestamp_str: str) -> str:
    """Convert ISO timestamp to relative time string."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
    except (ValueError, TypeError):
        return "unknown"


def show_status(state: dict, config: dict | None) -> None:
    """Display chain status and miner info."""
    chain = state["chain"]
    last = state["last_block"]
    token = state["token"]
    ledger = state["ledger"]

    console.print()
    console.print("[bold cyan]Kyrex Chain Status[/]")
    console.print("─" * 36)
    console.print(f"  Chain height:      [bold]{chain['height']}[/] blocks")
    console.print(f"  Current val_bpb:   [bold green]{chain['current_val_bpb']:.4f}[/]")
    console.print(f"  Total improvement: [bold]{chain['total_improvement_pct']:.2f}%[/]")
    console.print(f"  Last block by:     {last['miner_id']} ({time_ago(last['timestamp'])})")

    if config:
        miner_id = config["miner"]["id"]
        miner_data = ledger.get(miner_id, {})
        console.print()
        console.print(f"  [bold yellow]Your Miner:[/] {miner_id}")
        console.print(f"  Balance:           [bold yellow]{miner_data.get('balance', 0.0):.2f} KRX[/]")
        console.print(f"  Blocks mined:      {miner_data.get('blocks_mined', 0)}")

    console.print()
    console.print("  [dim]Network:[/]")
    console.print(f"    {len(ledger)} active miner{'s' if len(ledger) != 1 else ''}")
    console.print(f"    {chain['height']} total experiments")
    console.print(f"    {token['total_emitted']:,.2f} / {token['total_supply']:,} KRX emitted")
    console.print()


def show_log(blocks: list[dict], limit: int = 10, miner_filter: str | None = None) -> None:
    """Display block history."""
    if miner_filter:
        blocks = [b for b in blocks if b.get("miner") == miner_filter]

    blocks = list(reversed(blocks[-limit:]))

    if not blocks:
        console.print("[dim]No blocks found.[/]")
        return

    console.print()
    for b in blocks:
        height = b.get("height", "?")
        bpb = b.get("val_bpb_after", b.get("val_bpb_before", 0))
        imp = b.get("improvement", 0)
        imp_pct = (imp / b.get("val_bpb_before", 1)) * 100 if b.get("val_bpb_before") else 0
        miner = b.get("miner", "unknown")
        reward = b.get("reward", 0)
        commit = b.get("commit", "???????")[:7]
        ts = time_ago(b.get("timestamp", ""))
        desc = b.get("desc", "")

        if height == 0:
            color = "yellow"
        elif imp > 0.01:
            color = "green"
        else:
            color = "cyan"

        console.print(f"[bold {color}]Block #{height}[/] | val_bpb: {bpb:.4f} | Δ: -{imp:.4f} (-{imp_pct:.2f}%)")
        console.print(f"  Miner: {miner} | Reward: [yellow]{reward:.2f} KRX[/]")
        console.print(f"  Commit: [dim]{commit}[/] | {ts}")
        if desc:
            console.print(f'  [dim]"{desc}"[/]')
        console.print()


def show_leaderboard(state: dict) -> None:
    """Display token leaderboard."""
    ledger = state["ledger"]
    token = state["token"]

    if not ledger:
        console.print("[dim]No miners yet.[/]")
        return

    sorted_miners = sorted(ledger.items(), key=lambda x: x[1].get("total_earned", 0), reverse=True)

    table = Table(title="Kyrex Leaderboard", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Miner", style="bold")
    table.add_column("Blocks", justify="right")
    table.add_column("KRX Earned", justify="right", style="yellow")

    for i, (miner_id, data) in enumerate(sorted_miners, 1):
        table.add_row(
            str(i),
            miner_id,
            str(data.get("blocks_mined", 0)),
            f"{data.get('total_earned', 0.0):,.2f}",
        )

    console.print()
    console.print(table)
    console.print(f"\n  [dim]Total emitted: {token['total_emitted']:,.2f} / {token['total_supply']:,} KRX[/]")
    console.print()
