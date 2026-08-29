# TFX — Tech Reference

> Reference doc for the ML Engineering Design course. Module lessons link here for specs; the demos that exercise TFX live in the module `code/` folders (written in Pass 2). The no-infra restriction is lifted for this tool — see Requirements.

## What it is & when to reach for it

TensorFlow Extended (TFX) is a library of **ML pipeline components** (ExampleGen, StatisticsGen, SchemaGen, Transform, Trainer, Evaluator, Pusher) wired by channels. Reach for it when you want the canonical end-to-end ML pipeline shape — the promotion/release path (M13) and the retraining loop (M16). **Caveat:** TFX is TensorFlow-centric (`Transform` assumes TF.Transform; artifacts are TF `Example` protos).

## Specs & versions

| Item | Value |
|---|---|
| License | Apache-2.0 |
| Pin | `tfx==1.*` (+ TensorFlow; pin both) |
| API surface used | `tfx.components`, `tfx.orchestration.pipeline.Pipeline`, channels, runner choice |

## Requirements (infra)

- TFX is a library — the **orchestrator runner** is the infra:
  - `LocalDagRunner` → zero infra (in-process)
  - `AirflowDagRunner` / `KubeflowDagRunner` → needs that platform's machinery
  - `BeamDagRunner` → DirectRunner (local) or Dataflow (GCP)
- A **metadata store** (SQLite dev / MySQL-Postgres prod)
- An **artifact store** (local dir / GCS / S3)

## Setup / run skeleton

1. Define components and wire via channels (`example_gen.outputs['examples']`)
2. Construct `Pipeline(pipeline_name=…, components=[…], enable_cache=…)`
3. Run with the chosen runner (`python pipeline.py` locally; deploy the generated DAG otherwise)

## Working code (Pass 2)

- `modules/13-deployment-cicd/code/promotion_pipeline_tfx.py` — the canonical 7-component pipeline with the promotion gate as Evaluator/Pusher config
- `modules/16-drift-retraining/code/retraining_pipeline_tfx.py` — retrain trigger via fresh examples
- Full per-demo specs live in those modules' `💻 CODE (Pass 2)` blockquotes.

## Gotchas / failure modes

- Implicit TensorFlow commitment (TF.Transform, `Example` protos)
- Metadata store is the source of truth for artifacts — don't treat it as optional
- Cache invalidation: `enable_cache` must be understood before relying on it

## Sources

- TFX official docs (`tensorflow.org/tfx`)
