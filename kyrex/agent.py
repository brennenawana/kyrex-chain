"""AI agent integration for code mutation. Pluggable — supports Claude Code, manual editing, etc."""

import os
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()


def mutate_with_claude_code(repo_root: Path, recent_blocks: list[dict] | None = None) -> str | None:
    """Use Claude Code CLI to modify train.py. Returns description of change, or None on failure."""
    train_py = repo_root / "train.py"
    program_md = repo_root / "program.md"

    # Build context about recent experiments
    history_context = ""
    if recent_blocks:
        history_context = "\n\nRecent blocks on the chain:\n"
        for b in recent_blocks[-5:]:
            desc = b.get("desc", "no description")
            bpb = b.get("val_bpb_after", "?")
            imp = b.get("improvement", 0)
            history_context += f"  - Block #{b.get('height', '?')}: val_bpb={bpb}, Δ={imp:.4f}, \"{desc}\"\n"
        history_context += "\nAvoid repeating changes that didn't work. Try something different.\n"

    prompt = (
        f"Read program.md and train.py in the current directory. "
        f"Make one targeted improvement to train.py to lower val_bpb. "
        f"Only modify train.py — do not modify any other file. "
        f"After making the change, explain what you changed in one sentence."
        f"{history_context}"
    )

    console.print("[dim]  Calling Claude Code for mutation...[/]")

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            console.print(f"[red]  Claude Code failed (exit {result.returncode})[/]")
            if result.stderr:
                console.print(f"[dim]  {result.stderr[:200]}[/]")
            return None

        # Claude Code modifies train.py directly via its tools
        # The stdout contains its explanation
        explanation = result.stdout.strip()
        # Extract just the last sentence as description
        lines = [l.strip() for l in explanation.splitlines() if l.strip()]
        desc = lines[-1] if lines else "AI-generated mutation"
        # Truncate long descriptions
        if len(desc) > 120:
            desc = desc[:117] + "..."
        return desc

    except FileNotFoundError:
        console.print("[red]  'claude' CLI not found. Install Claude Code or use --manual.[/]")
        return None
    except subprocess.TimeoutExpired:
        console.print("[red]  Claude Code timed out (120s).[/]")
        return None


def mutate_with_editor(repo_root: Path) -> str | None:
    """Open train.py in $EDITOR for manual editing. Returns description or None."""
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    train_py = repo_root / "train.py"

    # Save original content to detect changes
    original = train_py.read_text()

    console.print(f"[yellow]  Opening train.py in {editor}...[/]")
    console.print("[dim]  Make your change, save, and close the editor.[/]")

    try:
        subprocess.run([editor, str(train_py)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        console.print(f"[red]  Editor failed: {e}[/]")
        return None

    new_content = train_py.read_text()
    if new_content == original:
        console.print("[dim]  No changes detected.[/]")
        return None

    # Ask for description
    desc = console.input("[yellow]  Describe your change: [/]").strip()
    return desc if desc else "Manual edit"


def mutate(repo_root: Path, provider: str = "claude", recent_blocks: list[dict] | None = None) -> str | None:
    """Run the configured agent to mutate train.py. Returns description or None."""
    if provider == "manual":
        return mutate_with_editor(repo_root)
    elif provider == "claude":
        return mutate_with_claude_code(repo_root, recent_blocks)
    else:
        console.print(f"[red]  Unknown agent provider: {provider}[/]")
        console.print("[dim]  Supported: claude, manual[/]")
        return None
