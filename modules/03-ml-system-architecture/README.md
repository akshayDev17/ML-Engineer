# M3 · ML System Architecture & the Reference Stack

> **Core question:** What are the parts of an ML system, and how do we reason about architecture decisions?

---

## From map to blueprint

M1 gave you the lifecycle (the *when*) and the anatomy (the *what*). M2 gave you the failure modes (the *why we care*). This module turns those into something you can design against: the **layer diagram in detail**, the **seams** between layers, the **ADR** discipline for recording decisions, and the **reference stack** — the concrete Python tooling we'll use for the rest of the course.

## The layer diagram, in detail

Every ML system, however bespoke, decomposes into the same six layers. What changes between systems is *how the layers are connected and where the seams are drawn* — and that's exactly what you'll be designing.

```mermaid
flowchart TB
    subgraph D["Data & Feature Layer"]
        D1["Ingestion & storage"] -->|"seam: data"| D2["Validation & quality gates"]
        D2 --> D3["Feature computation"]
        D3 --> D4["Feature store"]
    end
    subgraph M["Modeling Layer"]
        M1["Experimentation"] --> M2["Training"]
        M2 -->|"seam: model"| M3["Model registry"]
    end
    subgraph V["Verification Layer"]
        V1["Offline evaluation"] --> V2["Online evaluation / A-B"]
        V2 --> V3["Approval gate"]
    end
    subgraph S["Serving Layer"]
        S2["Deployment & CI-CD"] -->|"deploys"| S1["Serving system<br/>(live inference)"]
    end
    subgraph O["Operational Layer"]
        O1["Monitoring"] --> O2["Drift & retraining"]
        O2 --> O3["Governance"]
    end
    D4 -->|"seam: feature (training)"| M1
    D4 -->|"seam: feature (serving)"| S1
    M3 --> V1
    V3 -->|"seam: model (release)"| S2
    O1 -.->|"observes"| S1
    O1 -.->|"observes for drift"| D4
    O2 -.->|"triggers retrain"| M2
```

Two kinds of arrows, and the difference is the point of this module. 
- **Solid arrows are flow seams** — an artifact crosses a boundary under a contract: data enters the system, features flow to training and serving, the model flows from the registry through the gate into deployment. 
- **Dotted arrows are cross-cutting relationships** — monitoring *observes*, drift *triggers* retraining; they carry signals and controls, not artifacts.

And note where **live inference** happens: the **Serving system** box (S1). 
- Two things arrive there and meet 
    — **features** (via the feature seam, from the feature store) and 
    - a **model** (via the release path, from CI/CD). 
- Read the arrow direction carefully: it's **CI/CD → serving**, not serving → CI/CD. 
    - The deployment pipeline *puts the model into* serving; the Serving system is the box that actually runs the live prediction.

Each layer has a **single responsibility** and a **defined interface** to its neighbors. That's not bureaucracy — it's what makes failures *locatable*. When something breaks, you want to know *which* layer broke and *at which seam*, not "the ML is down."

## Coupling and seams

The most important architectural concept in ML systems is the **seam**: the boundary between two layers where a contract exists. A contract says: *this is the shape of what passes across this boundary, and if it changes, the change is explicit and versioned.*

Why seams matter so much here, specifically:

1. **ML systems change faster than normal systems.** Data changes, features change, models change, the world changes. Seams are where you *absorb* change without it silently propagating.
2. **Silent absorption is the enemy.** From M2: cascading failure happens when an upstream change flows downstream *unannounced*. A seam with a contract turns that silent flow into a *detected* event.

The three seams that matter most in practice — the three labeled in the diagram:

- **The data seam** — between ingestion and everything else. The contract: "this schema, these invariants, this freshness guarantee." Break it, and you get silent data corruption (M5).
- **The feature seam** — between feature computation and both training and serving. The contract: "features `x1..xn` are computed by *this* code, on *this* data, in *this* schema." Training and serving both consume *the same contract*. Break it, and you get training–serving skew (M6).
- **The model seam** — between the registry and everything that consumes the model (evaluation, deployment, serving). The contract: "a model is a versioned artifact with lineage; nothing is deployed that isn't registered." Break it, and you lose the answer to "what's in prod?" (M9, M13).

A seam is where an **artifact** crosses a boundary under a contract. That's what separates it from the **dotted arrows** — the cross-cutting relationships like *drift signal* and *retrain*. Those carry signals and controls (notifications, triggers), not artifacts, and are **not seams**: a drift signal has no shape contract that training and serving must both honor — it's observability saying "look here." Conflating the two — treating every arrow as a seam — is how the word loses its meaning.

> **⚠️ Failure mode** — *The seamless monolith.* A system where data flows from source to model with no explicit contracts works fine until it doesn't — and then the failure has no single location, because every layer silently assumed the one above it was right. The fix isn't more code; it's *seams with contracts*.

## ADRs: the tradeoff ledger, formalized

M1 introduced the tradeoff ledger. Its formal form is the **ADR — architecture decision record**. An ADR is a short document capturing one significant decision, the context, the options considered, and the consequences. It's not a spec; it's a *memory* of why the system is the way it is.

The template we'll use (a trimmed MADR-style format):

```
# ADR-001: <decision>

## Context
What problem are we solving? What constraints exist?

## Decision
What did we choose? (The actual decision, in one sentence.)

## Alternatives considered
- Option A — why not
- Option B — why not

## Consequences
- Good: what this buys us
- Bad: what this costs us (the tradeoff)
```

Every module from here on ends with design exercises that produce ADR-shaped thinking. When in doubt, the question is always: **"why this, and what does it give up?"**

> **⚖️ Tradeoff** — *Documenting vs. shipping.* ADRs feel like overhead, and they are — until the day you inherit a system with no record of why it's shaped the way it is, and every change is archaeology. The ledger entry: *chose to write ADRs, gave up some velocity, bought the ability to revisit decisions without reliving them.*

## The reference stack

A course is only concrete if it picks tools. We pick a **fixed, vendor-neutral Python stack** — the ML analog of the Harness Engineering course's "ADK + LiteLLM" choice. The principle: **no single-cloud assumption.** The concepts must transfer to whatever stack you actually run in production.

| Layer | Tool | What we use it for |
|---|---|---|
| Modeling (classical) | scikit-learn | Linear models, trees, ensembles, pipelines |
| Modeling (deep) | PyTorch | Neural networks when needed |
| Data validation | Pandera / Great Expectations | Schema contracts, quality gates |
| Experiment tracking & registry | MLflow | Params, metrics, artifacts, model versions |
| Serving | FastAPI + Docker | Online endpoints, containers |
| Serialization | ONNX, TorchScript | Portable model artifacts |
| Observability | Prometheus + Grafana | Metrics, dashboards, alerting |
| Drift detection | alibi-detect | Data/concept drift, PSI — code in Pass 2 |
| Orchestration | Prefect | Pipelines, scheduling — code in Pass 2 |

A note on depth: we reference these at the **API level** — enough to make a concept concrete, not enough to run a production platform. Labs are deferred; the point of the stack is to make every idea *runnable in your head*. Two rows are staged for Pass 2 — **Prefect** (orchestration) and **alibi-detect** (drift detection) — flagged with `💻 CODE (Pass 2)` blockquotes below; the code arrives in the second pass, and the design doesn't depend on it. The orchestration modules (M13, M16) also cover the platform alternatives — **Airflow, Kubeflow Pipelines, TFX** — whose specs/requirements live in the tech shelf ([`tech/`](../../tech/)), with the no-infra restriction lifted for those modules.

### Why this stack

- **scikit-learn + PyTorch** covers the full spectrum from "a logistic regression is the right answer" to "this genuinely needs a neural net." Choosing between them *is itself a design decision* (M8).
- **Pandera / Great Expectations** make validation a *contract you can execute*, not a hope (M5).
- **MLflow** is the de-facto standard for tracking and registry, and it's cloud-agnostic (M7, M9).
- **FastAPI + Docker** are the workhorses of online serving and are trivial to reason about (M12, M13).
- **Prometheus + Grafana** are the standard for metrics/alerting and are not ML-specific — which is the point: ML monitoring should plug into the *same* observability the rest of your org already runs, not a parallel island (M15).
- **ONNX/TorchScript** make a model portable between training and serving runtimes — the serialization half of the feature seam (M12).
- **Prefect** makes orchestration a *few decorators of Python*, not a platform: flows, tasks, retries, and schedules are concepts you can see in ten lines — and it runs locally with zero infrastructure (M13, M16).
- **alibi-detect** packages drift detection (KS, chi-squared, MMD) behind a fit-on-reference / predict-on-new-data API — the M16 concept, in library form.

> **💻 CODE (Pass 2) · Prefect** — *orchestration, made concrete.* The working demo is M13's promotion pipeline (`modules/13-deployment-cicd/code/promotion_dag.py`) plus the retraining variant in M16. Specs live in those modules' blockquotes; base reference: [`tech/prefect.md`](../../tech/prefect.md).

> **💻 CODE (Pass 2) · alibi-detect** — *drift detection, made concrete.* The working demo is M16's detector (`modules/16-drift-retraining/code/drift_detector.py`) plus M15's alerting wiring. Specs live in those modules' blockquotes; base reference: [`tech/alibi-detect.md`](../../tech/alibi-detect.md).

> **🐍 Reference stack at a glance** — The one tool that matters *right now* is **MLflow**: from M7 onward, every experiment we discuss is tracked, every model is registered, and "which model is in prod?" always has an answer. If you internalize one tool this course, make it MLflow.

## The first ADR

The rest of the course assumes this stack. Let's record that assumption the way we'd want it recorded in a real system — as an ADR — so you can see the discipline in action.

```
# ADR-001: Vendor-neutral Python reference stack

## Context
The course needs a concrete, runnable-in-your-head stack to make
concepts real, but must transfer to any production environment.

## Decision
Use scikit-learn + PyTorch for modeling, Pandera/Great Expectations
for validation, MLflow for tracking/registry, FastAPI + Docker for
serving, ONNX/TorchScript for serialization, Prometheus/Grafana for
observability, Prefect for orchestration, and alibi-detect for drift detection.

## Alternatives considered
- Single-cloud stack (e.g., all-AWS SageMaker) — simpler but vendor-locks the concepts
- No stack, pure concepts — transfers but stays too abstract to be useful

## Consequences
- Good: transferable, industry-standard, every concept has a concrete surface
- Bad: not an optimized "one-click" platform; orchestration and drift-detection code arrives in Pass 2
```

That's the template. You'll write your own before long.

## Design exercise

This is the module where you start *producing*, not just reading.

**Part A — Draw your own system.** Take the ML product you dissected in M1 and draw its layer diagram. Don't copy the generic one — draw *your product's* actual data sources, features, model, serving path, and monitoring (or the absence of monitoring, which is itself a finding). Mark every seam where you think a contract exists or *should* exist.

**Part B — Find the missing seam.** Identify the one boundary in your diagram where data flows with no explicit contract today. Write the contract that should exist there: what's the shape, the invariants, and what happens when it's violated?

**Part C — Write ADR-000.** Write your first ADR, in the template above, for one *real* decision you'd make about your product's architecture (not the course's stack — yours). It can be anything: "we'll serve batch rather than online," "we'll use a feature store," "we'll treat the model as retrainable monthly." The only requirement: it must state the tradeoff honestly in the Consequences section.

The goal is to leave this module with the reflex: **a design is a set of seams and a stack of ADRs.** Everything else is implementation.

---

*Next: Part 1 — the Data & Feature Layer. M4 · Data Engineering I: Ingestion, Storage & Point-in-Time Correctness — where training data actually comes from, and how to keep it temporally honest.*
