# M13 · code/ — Pass 2 demos

Working code for this module's demos lands here in **Pass 2** — nothing here yet by design (the design pass comes first).

Each file's spec (demonstrates / requirements / accept) is captured in the `💻 CODE (Pass 2)` blockquotes in [`../README.md`](../README.md). Base references: [`tech/prefect.md`](../../tech/prefect.md), [`tech/airflow.md`](../../tech/airflow.md), [`tech/kubeflow-pipelines.md`](../../tech/kubeflow-pipelines.md), [`tech/tfx.md`](../../tech/tfx.md).

**Planned files:**

| File | Demonstrates |
|---|---|
| `promotion_dag.py` | Prefect flow: staging → shadow → canary → prod with guardrail gating + auto-rollback (no-infra path) |
| `promotion_dag_airflow.py` | The same promotion pipeline as an Airflow DAG (infra path) |
| `promotion_pipeline_kfp.py` | The same promotion pipeline as KFP components (K8s path) |
| `promotion_pipeline_tfx.py` | The promotion path as a TFX pipeline (Evaluator/Pusher as the gate) |
