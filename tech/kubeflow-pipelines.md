# Kubeflow Pipelines — Tech Reference

> Reference doc for the ML Engineering Design course. Module lessons link here for specs; the demos that exercise KFP live in the module `code/` folders (written in Pass 2). The no-infra restriction is lifted for this tool — see Requirements.

## What it is & when to reach for it

Kubeflow Pipelines (KFP) is the Kubernetes-native ML pipeline platform: each pipeline step is a **container op** executed as a K8s pod, orchestrated by Argo Workflows. Reach for it when you're already on Kubernetes and want per-step isolation/reproducibility — the promotion pipeline (M13) and the retraining loop (M16).

## Specs & versions

| Item | Value |
|---|---|
| License | Apache-2.0 |
| Pin | KFP 2.x (server + `kfp` SDK 2.x) |
| API surface used | `@dsl.component` (containerized functions), `@dsl.pipeline`, `dsl.Input/Output`, compile → YAML |

## Requirements (infra)

- A **Kubernetes cluster** (k3s/minikube locally; EKS/GKE/AKS otherwise)
- **KFP standalone install** on it: api-server + persistence (MinIO + MySQL) + Argo Workflows engine
- A **container registry** — every component is packaged as a container image

## Setup / run skeleton

1. Provision cluster; install KFP standalone manifests
2. Define components with `@dsl.component(base_image=…, packages_to_install=[…])`
3. `kfp.compiler.Compiler().compile(pipeline_func, "pipeline.yaml")`
4. `kfp.Client().create_run_from_pipeline_func(...)` or upload via UI

## Working code (Pass 2)

- `modules/13-deployment-cicd/code/promotion_pipeline_kfp.py` — promotion gates as components
- `modules/16-drift-retraining/code/retraining_pipeline_kfp.py` — drift-triggered retrain components
- Full per-demo specs live in those modules' `💻 CODE (Pass 2)` blockquotes.

## Gotchas / failure modes

- Code only runs on a cluster — local dev needs k3s/minikube
- v1 → v2 transition: author for the v2 DSL/IR model
- Each component needs its own image + installed packages — dependency management per step

## Sources

- Kubeflow Pipelines official docs (`kubeflow.org/docs/components/pipelines`)
