# M16 · code/ — Pass 2 demos

Working code for this module's demos lands here in **Pass 2** — nothing here yet by design.

Each file's spec is captured in the `💻 CODE (Pass 2)` blockquotes in [`../README.md`](../README.md). Base references: [`tech/alibi-detect.md`](../../tech/alibi-detect.md), [`tech/prefect.md`](../../tech/prefect.md), [`tech/airflow.md`](../../tech/airflow.md), [`tech/kubeflow-pipelines.md`](../../tech/kubeflow-pipelines.md), [`tech/tfx.md`](../../tech/tfx.md).

**Planned files:**

| File | Demonstrates |
|---|---|
| `drift_detector.py` | alibi-detect `KSDrift` fit/predict — the library form of the inline PSI (per-feature p-values + threshold) |
| `retraining_dag.py` | Prefect flow: drift-check gating retrain → evaluate → promote, scheduled (no-infra path) |
| `retraining_dag_airflow.py` | The retraining loop as an Airflow DAG (infra path) |
| `retraining_pipeline_kfp.py` | The retraining loop as KFP components (K8s path) |
| `retraining_pipeline_tfx.py` | The retraining loop as a TFX pipeline (fresh examples trigger retrain) |
