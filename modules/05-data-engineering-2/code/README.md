# M5 · code/ — ingestion validation pipeline (runnable)

A realistic, minimal ingestion pipeline: a schema contract, batch + stream
gates, and the two entry points that actually run them. No tests — the
runners ARE the demonstration.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install "pandas>=2,<3" pandera
```

## Run

```bash
# 1. simulate a raw feed to disk (clean, and one that "goes bad")
python simulate.py --out data --n 200 --bad 4

# 2. batch job: validate the contaminated feed, split clean vs quarantine
python run_batch.py --input data/transactions_contaminated.csv

# 3. stream consumer: same feed, processed window-by-window, routed clean/DLQ
python run_stream.py --input data/transactions_contaminated.csv --window-size 50
```

Outputs land in `out/` (batch: `batch_clean.csv`, `batch_quarantine.csv`,
`batch_failures.csv`; stream: `stream_clean.csv`, `stream_dlq.csv`).

## Layout

| File | What it is |
|---|---|
| `schemas/transactions.py` | The `Transaction` DataFrameModel — the schema contract |
| `gates/batch_ingestion.py` | `validate_batch()` + `GateResult` — the batch gate |
| `gates/stream_ingestion.py` | `process_window()` — the stream gate |
| `ingest.py` | `read_transactions()` + the dtype contract (CSV loses types; re-declared on read) |
| `simulate.py` | Generates raw feeds to disk (clean + contaminated) |
| `run_batch.py` | **Batch job entry point** — the thing you actually run |
| `run_stream.py` | **Stream consumer entry point** — the thing you actually run |

## The two-feed scenario

`simulate.py` writes two files: a **clean** feed (every row valid) and a
**contaminated** feed (the clean feed plus injected rule-violating rows).
Run the batch job or stream consumer against each to watch the gate pass
clean data untouched and split/quarantine the bad rows.
