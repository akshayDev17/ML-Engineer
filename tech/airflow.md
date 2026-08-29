# Airflow — Tech Reference

> Reference doc for the ML Engineering Design course. Module lessons link here for specs; the demos that exercise Airflow live in the module `code/` folders (written in Pass 2). The no-infra restriction is lifted for this tool — see Requirements.

## What it is & when to reach for it

Apache Airflow is the industry-standard workflow orchestrator: Python DAG files executed by a persistent scheduler. Reach for it when you already run Airflow (or want the org-default choice) for batch-oriented pipelines — the promotion pipeline (M13) and the retraining loop (M16).

## Specs & versions

| Item | Value |
|---|---|
| License | Apache-2.0 |
| Pin | Airflow 2.x (`apache-airflow==2.10.*` + needed provider packages) |
| API surface used | TaskFlow API (`@dag` / `@task`), `schedule`, connections, operators |

## Requirements (infra)

- Scheduler + webserver + **metadata DB** (Postgres/MySQL; SQLite dev-only)
- Executor: `LocalExecutor` (dev) · `CeleryExecutor` (needs Redis/RabbitMQ broker + workers) · `KubernetesExecutor`
- Recommended local shape: the official `docker-compose` (postgres, scheduler, webserver, worker)
- DAG sync (volume mount or git-sync); log storage (local / S3 / GCS)
- Airflow **connections** to MLflow, the feature store, the serving API

## Setup / run skeleton

1. `docker compose up` with the official Airflow image
2. Mount / sync the `dags/` folder
3. `airflow dags trigger <dag_id>` (or UI) — each run is recorded in the metadata DB

## Working code (Pass 2)

- `modules/13-deployment-cicd/code/promotion_dag_airflow.py` — promotion pipeline as a DAG
- `modules/16-drift-retraining/code/retraining_dag_airflow.py` — drift-triggered retrain DAG
- Full per-demo specs (demonstrates / requirements / accept) live in those modules' `💻 CODE (Pass 2)` blockquotes.

## Gotchas / failure modes

- DAG files are parsed on the scheduler heartbeat — keep them static and import-safe
- A DAG only means something inside a running Airflow environment
- Batch-scheduling mental model fights stateful, gated flows — encode gates as task conditions

## Sources

- Apache Airflow official docs (`airflow.apache.org`)
