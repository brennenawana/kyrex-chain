# Kyrex Mining Guide

## What is mining?

In Kyrex, mining means running ML experiments that improve a shared
language model. Instead of wasting compute on hash puzzles (like Bitcoin),
your GPU does useful work — training neural networks.

The metric is **val_bpb** (validation bits per byte). Lower is better.
Every time you push val_bpb lower, you've mined a block and earned KRX.

## Setup

### Hardware

You need an NVIDIA GPU. Any generation works, but faster GPUs find
improvements faster:

| GPU | Speed | Notes |
|-----|-------|-------|
| H100 | Fastest | Flash Attention 3 native |
| A100 | Fast | Great for mining |
| RTX 4090 | Fast | Consumer king |
| RTX 3090 | Moderate | Still profitable |

### Software

```bash
# 1. Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the chain
git clone https://github.com/brennenawana/kyrex-chain.git
cd kyrex-chain

# 3. Install dependencies
uv sync

# 4. Download training data + build tokenizer (~2 minutes)
uv run prepare.py

# 5. Verify your GPU works (runs a 5-minute baseline)
uv run train.py
```

The last command should finish and print something like:

```
---
val_bpb:          0.997900
training_seconds: 300.1
...
```

If you see `val_bpb` printed, your setup works.

## The Mining Loop

### Manual mining (no CLI yet)

Until the `kyrex` CLI is built, you can mine manually:

```bash
# 1. Pull latest chain state
git pull --ff-only origin main

# 2. Check current val_bpb
python -c "import json; print(json.load(open('kyrex.json'))['chain']['current_val_bpb'])"

# 3. Edit train.py with an improvement idea
#    (change hyperparameters, model architecture, optimizer, etc.)

# 4. Run the experiment (5 minutes)
uv run train.py 2>&1 | tee run.log

# 5. Check the result
grep "^val_bpb:" run.log

# 6. If val_bpb improved:
#    - Update kyrex.json with new state
#    - Append to history/blocks.jsonl
#    - Commit and push
#
# If val_bpb did NOT improve:
#    - Revert train.py: git checkout train.py
#    - Try a different idea
```

### With the kyrex CLI (coming soon)

```bash
# Initialize your miner identity
kyrex init --name "your-name" --gpu "RTX 4090"

# Start autonomous mining
kyrex mine

# Or run a single experiment without pushing
kyrex mine --dry-run

# Check status
kyrex status
kyrex log
kyrex leaderboard
```

## What to change

`train.py` is the only file you modify. Everything is fair game:

- **Model architecture**: depth, width, attention heads, window patterns
- **Optimizer**: learning rates, betas, weight decay, warmup/cooldown
- **Training**: batch size, gradient accumulation, scheduling
- **Activation functions**: ReLU², GELU, SwiGLU, etc.
- **Anything else**: as long as it runs and finishes in 5 minutes

### Ideas that tend to work

- Adjusting learning rate (often the highest-leverage knob)
- Changing model depth vs width ratio
- Tuning the warmup/cooldown schedule
- Modifying the optimizer (e.g., different momentum settings)
- Removing complexity that isn't helping

### Ideas to be careful with

- Dramatically increasing model size (may OOM or train too few steps)
- Adding new dependencies (not allowed)
- Modifying `prepare.py` (not allowed, changes will be rejected)

## Race Resolution

If two miners find improvements simultaneously:

1. First to push wins — their commit becomes the new chain tip
2. The loser's push gets rejected (not fast-forward)
3. The loser must pull the new tip and **start a fresh experiment**
4. You can't rebase ML experiments — the code changed underneath you

This is analogous to Bitcoin miners discarding partial work when someone
else finds a block first.

## Rewards

```
Block reward = 50 KRX × improvement_multiplier

Multiplier:
  ≥5% improvement → 5x (250 KRX)
  ≥1% improvement → 2x (100 KRX)
  <1% improvement → 1x (50 KRX)

Halving: reward halves every 210,000 blocks
```

For v0.2, the full reward goes to the miner. Future versions will split:
60% miner, 20% verifiers, 15% GPU pool, 5% treasury.

## Verification

Any miner can verify a block by re-running the experiment:

```bash
kyrex verify <commit-hash>
```

This checks out the parent commit's code, applies the diff, runs training,
and compares the reproduced val_bpb to the claimed value (within ±0.5%
tolerance for ML non-determinism).

## FAQ

**Q: Do I need an AI agent to mine?**
No. You can edit `train.py` by hand. The AI agent just automates the
"think of an improvement" step.

**Q: What if my GPU is slow?**
Slower GPUs train fewer steps in 5 minutes, so they achieve higher
(worse) val_bpb. But improvements are relative — if you find a change
that helps on any GPU, it likely helps on all GPUs.

**Q: Can I mine on CPU?**
No. The training code requires CUDA (NVIDIA GPU).

**Q: What happens if the chain gets stuck?**
If val_bpb stops improving, the network has hit a plateau. This is
natural — it means the model is approaching optimal for the current
architecture. Try more radical changes (different architecture, etc.).
