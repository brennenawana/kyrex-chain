# Kyrex — Decentralized ML Research Mining

Mine KRX tokens by improving a shared AI model. Every improvement you
find becomes a block on the chain.

## How it works

This repo IS the blockchain. Commits are blocks. `main` is the canonical
chain. `kyrex.json` is the ledger. `train.py` is the evolving model code.

Miners compete to improve `val_bpb` (validation bits per byte) — a
vocabulary-size-independent metric for language model quality. Lower is better.

Each experiment runs for exactly **5 minutes** on a single GPU. If you
find an improvement, you commit it and push. If someone else pushes first,
you discard and start fresh from the new chain tip.

## Quick Start

### Prerequisites

- NVIDIA GPU (any — H100, A100, RTX 4090/3090, etc.)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### 1. Clone the chain

```bash
git clone https://github.com/xargzx/kyrex-chain.git
cd kyrex-chain
```

### 2. Install dependencies

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

### 3. Prepare data (one-time, ~2 min)

```bash
uv run prepare.py
```

### 4. Initialize your miner

```bash
kyrex init --name "your-name" --gpu "RTX 4090"
```

### 5. Start mining

```bash
kyrex mine
```

That's it. Kyrex will:
- Pull the latest chain state
- Run an AI agent that modifies the training code
- Train for exactly 5 minutes
- If performance improved → commit + push (you earn KRX)
- If not → discard and try again
- Loop forever

### Check your status

```bash
kyrex status
kyrex log
kyrex leaderboard
```

## Architecture

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Miner A  │  │ Miner B  │  │ Miner C  │  ... N miners
│ RTX 4090 │  │ H100     │  │ A100     │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │
     ▼              ▼              ▼
┌─────────────────────────────────────────┐
│          This GitHub Repo              │  ← The "chain"
│  main branch = canonical chain tip     │
│  each commit = a verified block        │
│  kyrex.json = chain state / ledger     │
│  train.py = evolving model code        │
└─────────────────────────────────────────┘
```

## Token Economics

- **Total supply**: 21,000,000 KRX
- **Block reward**: 50 KRX (halves every 210,000 blocks)
- **Improvement bonus**: 5x for >5% improvement, 2x for >1%

See [MINING.md](MINING.md) for the full mining guide.

## Credits

Training code based on [karpathy/autoresearch](https://github.com/karpathy/autoresearch).
Protocol design: [Kyrex Whitepaper](https://github.com/xargzx/kyrex/blob/main/kyrex-whitepaper.md).
