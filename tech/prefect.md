# Prefect — Tech Reference

> Reference doc for the ML Engineering Design course. Module lessons link here for specs; the demos that exercise Prefect live in the module `code/` folders (written in Pass 2). Runs locally — **no infra required**.

## What it is & when to reach for it

Prefect is a Python-native workflow orchestrator: `@flow` / `@task` decorators turn functions into a DAG with retries, caching, and schedules. Reach for it when you want the orchestration *concept* without platform machinery — the promotion pipeline (M13) and the retraining loop (M16) in their no-infra form. Free open source (Apache-2.0).

## Specs & versions

| Item | Value |
|---|---|
| License | Apache-2.0 |
| Pin | Prefect 3.x (`prefect==3.*`) |
| API surface used | `@flow`, `@task`, `retries`/`retry_delay_seconds`, conditional gating, `flow.serve(cron=…)` |

## Requirements

- `pip install prefect` — that's it. Runs in-process; the Prefect server is optional (needed only for the UI/scheduling persistence).

## Setup / run skeleton

1. Define tasks with `@task`, compose with `@flow`
2. Run directly (`flow(...)`) or schedule (`flow.serve(name=…, cron=…)`)

## Working code (Pass 2)

- `modules/13-deployment-cicd/code/promotion_dag.py` — promotion gates (staging → shadow → canary → prod) as a flow
- `modules/16-drift-retraining/code/retraining_dag.py` — drift-check gating retrain → evaluate → promote
- Full per-demo specs live in those modules' `💻 CODE (Pass 2)` blockquotes.

## Gotchas / failure modes

- Conditional gating is Python `if` inside the flow — keep task boundaries explicit
- Scheduling persistence needs the server; pure `flow()` runs don't

## Sources

- Prefect official docs (`docs.prefect.io`)
