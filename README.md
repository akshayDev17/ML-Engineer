# ML Engineering Design

**Designing the Systems Around Machine-Learned Models**

A self-study course for working professionals who can train models in a notebook but want to design *production* ML systems end-to-end.

> The model is not the product — the system is. This course teaches you to treat the system around the model as the primary engineering artifact: data & feature pipelines, experimentation, evaluation, serving, monitoring, and governance — with every decision made deliberately and recorded as a tradeoff.

## What this course is

- **Design-first, not algorithm-first.** The emphasis is on architecture, requirements, and trade-offs — not on re-deriving ML math.
- **End-to-end.** It covers the full production ML lifecycle, including MLOps (CI/CD), deployment, observability, drift, and governance.
- **Failure-driven.** Every module exists to prevent a specific production failure mode (leakage, skew, drift, feedback loops, silent degradation).
- **Vendor-neutral Python.** scikit-learn + PyTorch, Pandera/Great Expectations, MLflow, FastAPI + Docker, Prometheus/Grafana. No single-cloud assumption.

## What this course is *not* (yet)

- **No labs** — full coded demos are deferred to a second pass (`💻 CODED DEMO (Pass 2)` placeholders mark where they'll go).
- **No assessment** — deferred.
- **No capstone decision** — deferred (see M18).

## Structure

18 modules in 6 parts, following the production ML lifecycle.

| Part | Modules | Theme |
|---|---|---|
| 0 | [M1](modules/01-what-is-an-ml-system/README.md) · [M2](modules/02-ml-failure-science/README.md) · [M3](modules/03-ml-system-architecture/README.md) | Foundations — the lifecycle, failure science, architecture & stack |
| 1 | [M4](modules/04-data-engineering-1/README.md) · [M5](modules/05-data-engineering-2/README.md) · [M6](modules/06-feature-pipelines/README.md) | The Data & Feature Layer |
| 2 | [M7](modules/07-experimentation-reproducibility/README.md) · [M8](modules/08-training-infrastructure/README.md) · [M9](modules/09-model-registry/README.md) | The Modeling Layer |
| 3 | [M10](modules/10-offline-evaluation/README.md) · [M11](modules/11-online-evaluation-ab/README.md) | The Verification Layer |
| 4 | [M12](modules/12-serving-architectures/README.md) · [M13](modules/13-deployment-cicd/README.md) · [M14](modules/14-scaling-optimization/README.md) | The Serving Layer |
| 5 | [M15](modules/15-monitoring-observability/README.md) · [M16](modules/16-drift-retraining/README.md) · [M17](modules/17-governance-security-cost/README.md) | The Operational Layer |
| 6 | [M18](modules/18-end-to-end-design/README.md) | Synthesis — a complete worked design |

## How to use this course

1. Read the modules in order — each builds on the last, and the failure-class → layer map recurs throughout.
2. Do the **design exercise** at the end of every module. They're paper-based; the point is the *thinking*, not the code.
3. Track your decisions in the **tradeoff ledger** discipline (and ADR format) introduced in M3.
4. When a module marks `💻 CODED DEMO (Pass 2)`, note the concept — the code comes in the second pass.

## Reference stack

- scikit-learn
- PyTorch 
- Pandera / Great Expectations 
- MLflow 
- FastAPI 
- Docker 
- ONNX / TorchScript 
- Prometheus 
- Grafana 
- alibi-detect (drift detection)
- Prefect (orchestration)

## Tech references

Specs, versions, requirements, and setup for the tools behind the stack — the reference shelf module lessons link out to. Working demos that exercise them land in each module's `code/` folder during Pass 2.

- [Airflow](tech/airflow.md) — promotion pipeline (M13) & retraining loop (M16), infra path
- [Kubeflow Pipelines](tech/kubeflow-pipelines.md) — same concepts, Kubernetes path
- [TFX](tech/tfx.md) — same concepts, canonical component graph
- [Prefect](tech/prefect.md) — orchestration concept, no-infra path
- [alibi-detect](tech/alibi-detect.md) — drift detection (M15, M16)

## Status

**All 18 modules are written.** See [syllabus.md](syllabus.md) for the full blueprint and conventions. The capstone decision (M18) is deferred, and full coded demos remain a second pass (`💻 CODED DEMO (Pass 2)`).
