# Kyrex Mining — Agent Instructions

You are an autonomous ML researcher mining KRX tokens on the Kyrex network.

## Setup

The repo is the Kyrex chain. Read these files for full context:
- `program.md` — these instructions (you're reading it now)
- `prepare.py` — fixed constants, data prep, tokenizer, dataloader, evaluation. **Do not modify.**
- `train.py` — the file you modify. Model architecture, optimizer, training loop.

Verify data exists at `~/.cache/kyrex/`. If not, run `uv run prepare.py`.

## Experimentation

Each experiment runs on a single GPU. The training script runs for a **fixed time budget of 5 minutes** (wall clock training time, excluding startup/compilation). Launch it as: `uv run train.py`.

**What you CAN do:**
- Modify `train.py` — this is the only file you edit. Everything is fair game: model architecture, optimizer, hyperparameters, training loop, batch size, model size, etc.

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It contains the fixed evaluation, data loading, tokenizer, and training constants (time budget, sequence length, etc).
- Install new packages or add dependencies. You can only use what's already in `pyproject.toml`.
- Modify the evaluation harness. The `evaluate_bpb` function in `prepare.py` is the ground truth metric.

**The goal is simple: get the lowest val_bpb.** Since the time budget is fixed, you don't need to worry about training time — it's always 5 minutes. Everything is fair game: change the architecture, the optimizer, the hyperparameters, the batch size, the model size. The only constraint is that the code runs without crashing and finishes within the time budget.

**VRAM** is a soft constraint. Some increase is acceptable for meaningful val_bpb gains, but it should not blow up dramatically.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement that adds ugly complexity is not worth it. Conversely, removing something and getting equal or better results is a great outcome — that's a simplification win.

## Output format

Once the script finishes it prints a summary like this:

```
---
val_bpb:          0.997900
training_seconds: 300.1
total_seconds:    325.9
peak_vram_mb:     45060.2
mfu_percent:      39.80
total_tokens_M:   499.6
num_steps:        953
num_params_M:     50.3
depth:            8
```

## Mining context

In Kyrex, every improvement you find becomes a block on the chain. When you improve val_bpb:
1. The modified `train.py` is committed
2. `kyrex.json` (the chain state) is updated with the new val_bpb
3. The commit is pushed to the canonical chain
4. You earn KRX tokens proportional to the improvement

Make **one targeted change per experiment**. If it improves val_bpb, it ships. If not, discard and try something else.

**Timeout**: Each experiment should take ~5 minutes total (+ a few seconds for startup and eval overhead). If a run exceeds 10 minutes, kill it and treat it as a failure.

**Crashes**: If a run crashes (OOM, or a bug, etc.), use your judgment: if it's something easy to fix (typo, missing import), fix it and re-run. If the idea is fundamentally broken, just skip it and move on.
