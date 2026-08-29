# ML Engineering Design — Course Blueprint (v0.1)

**Course title:** ML Engineering Design: Designing the Systems Around Machine-Learned Models \
**Audience:** Working professional, self-study (~4–6 years experience; comfortable in Python, has trained models in notebooks, has *not* designed or operated a production ML system) \
**Format:** Rich written Markdown lessons — broad, deep, vivid. No time constraint. No lab infrastructure for now (inline Python examples yes, full coded demos deferred to Pass 2). Design exercises end every module. \
**Reference stack:** Vendor-neutral Python — scikit-learn + PyTorch (modeling), Pandera / Great Expectations (data validation), MLflow (tracking & registry), FastAPI + Docker (serving), Prometheus + Grafana (observability), Prefect (orchestration), alibi-detect (drift detection). No single-cloud assumption. Orchestration and drift-detection code arrives in Pass 2. \
**Out of scope:** ML theory/math (assumes basic ML literacy), novel model research, general software-engineering basics, pure data/platform infrastructure beyond what ML systems need, frontend/product design.

---

## 1. Why this course exists

The model is not the product — the system is. A trained model is a *component*, not a product. What turns it into a reliable, governed, observable product is the deliberate design of everything around it: the data pipelines that feed it, the features that describe the world, the training process that reproduces it, the evaluation that vets it, the serving layer that exposes it, and the monitoring that keeps it honest.

This course teaches you to think like an ML systems engineer: treat the system *around* the model as the primary engineering artifact, and make deliberate, reviewable decisions about every layer — the same rigor you already apply to distributed systems, applied now to ML. The lifecycle is the spine: problem framing → data → features → training → evaluation → serving → monitoring, looping back on itself.

### What an ML system is (and isn't)
- **Is:** the set of systems *you design* to produce, verify, serve, and observe model predictions — data & feature pipelines, training & experimentation, evaluation, serving, monitoring, governance.
- **Isn't:** "everything except the model," nor "a notebook that scored 0.95." Leaving the surrounding system undesigned is not ML engineering. (See: [Hidden Technical Debt in Machine Learning Systems](https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html))

---

## 2. Learning outcomes

By the end of this course, the learner will be able to:

1. **Frame** a business problem as a production ML problem with measurable success criteria and non-functional requirements (latency, throughput, cost, fairness, privacy).
2. **Design** data and feature pipelines with validation gates, point-in-time correctness, and no training–serving skew.
3. **Run** a reproducible modeling effort — experimentation, tracking, baselines, model registry — and justify model choices from requirements, not defaults.
4. **Evaluate** models honestly: leakage-free validation, the offline–online gap, and A/B testing with guardrails and approval gates.
5. **Architect** a serving system — batch / online / streaming / edge — with a deployment strategy, CI/CD, and rollback.
6. **Operate** an ML system: monitoring, observability, drift detection, retraining triggers, and incident response.
7. **Govern** an ML system: lineage, compliance, fairness, security, and cost — and know which risks remain genuinely open.

---

## 3. Module map — 18 modules in 6 parts

> Every module carries three cross-cutting threads: **(1) Failure modes** — how this layer breaks in production; **(2) The tradeoff ledger** — the decisions and their costs; **(3) Reference stack at a glance** — the Python-level surface that implements the concepts. Example domains vary per module.

**Status legend:** ✅ written · 🚧 in progress · ⬜ planned

| Module | Status | Module | Status |
|---|---|---|---|
| M1 · What Is an ML System | ⬜ | M10 · Offline Evaluation | ⬜ |
| M2 · ML Failure Science | ⬜ | M11 · Online Evaluation, A/B Testing & Approval Gates | ⬜ |
| M3 · ML System Architecture & Reference Stack | ⬜ | M12 · Serving Architectures | ⬜ |
| M4 · Data Engineering I — Ingestion, Storage & Point-in-Time | ⬜ | M13 · Deployment Strategies & CI/CD | ⬜ |
| M5 · Data Engineering II — Quality & Validation | ⬜ | M14 · Scaling, Optimization & Cost | ⬜ |
| M6 · Feature Pipelines & the Feature Store | ⬜ | M15 · Monitoring & Observability | ⬜ |
| M7 · Experimentation & Reproducibility | ⬜ | M16 · Drift, Retraining & Feedback Loops | ⬜ |
| M8 · Training Infrastructure & Model Selection | ⬜ | M17 · Governance, Security & Cost | ⬜ |
| M9 · The Model Registry & Lifecycle | ⬜ | M18 · End-to-End Design | ⬜ |

### Part 0 — Foundations (what we're building and why)

**M1 · What Is an ML System?**
- *Core question:* What exactly is the engineering artifact we're designing?
- The model-is-not-the-product thesis; the notebook → production gap
- The production ML lifecycle (CRISP-ML(Q)-adapted) as the course spine: framing → data → features → training → evaluation → serving → monitoring
- System anatomy in one picture: data · features · training · evaluation · serving · monitoring
- ML system vs. ML model vs. ML platform — the vocabulary trap
- A taxonomy of production failure modes (leakage, skew, drift, feedback loops, silent degradation)
- *Domain:* survey across fraud / recommendation / search products; *Exercise:* dissect one ML product you use into the system anatomy; locate where value and risk live

**M2 · ML Failure Science**
- *Core question:* What does a production ML system actually do wrong, and why — before we design anything?
- Failure taxonomy: data leakage, training–serving skew, data/concept drift, feedback loops, silent model degradation, cascading failures
- Why "the model got worse" is almost always "the system around it changed" — failure attribution
- Failure classes as design inputs: each class maps to a system layer (this mapping recurs through the whole course)
- Real incident postmortems of public ML failures (Zillow Offers, pricing-model decay, healthcare model drift, etc.)
- *Domain:* failure case studies across domains; *Exercise:* for each failure class, name the layer that should have caught it

**M3 · ML System Architecture & the Reference Stack**
- *Core question:* What are the parts of an ML system, and how do we reason about architecture decisions?
- The layer diagram in detail; coupling and seams between layers
- ADR (architecture decision record) discipline — every module's tradeoffs get recorded this way
- The Python reference stack at a glance: sklearn/PyTorch, Pandera/Great Expectations, MLflow, FastAPI + Docker, Prometheus/Grafana — how the pieces map to the stack
- Why vendor-neutral Python (no single-cloud assumption) for the rest of the course
- *Domain:* a minimal "fraud scoring" system; *Exercise:* write the first ADR — "why this stack, why this seam structure"

### Part 1 — The Data & Feature Layer (what the model learns from)

**M4 · Data Engineering I — Ingestion, Storage & Point-in-Time Correctness**
- *Core question:* Where does training/serving data come from, and how do we keep it temporally honest?
- Sources & ingestion: batch vs streaming; the cost of "real-time"
- Storage choices: lake / warehouse / feature store; hot vs cold paths
- Point-in-time correctness: building training sets that don't look into the future
- Label sources & label quality; weak supervision (brief)
- *Domain:* e-commerce recommendation data; *Exercise:* design ingestion + point-in-time joins for a recommendation training set; list where leakage creeps in

**M5 · Data Engineering II — Quality & Validation**
- *Core question:* How do we catch bad data before it poisons a model?
- Data contracts & schema validation; quality gates in pipelines
- Drift at ingestion; anomaly detection on raw inputs
- Data documentation & lineage (where did this column come from?)
- Monitoring data quality as a first-class concern
- *Domain:* fintech transaction data; *Exercise:* write the validation-gate spec (schemas, ranges, invariants) for a transaction pipeline; adversarially review it

**M6 · Feature Pipelines & the Feature Store**
- *Core question:* How do features get computed consistently in training and serving?
- Feature engineering at scale; the feature as the unit of reuse
- Training–serving skew: same code path, same features, same preprocessing
- Feature stores: what they standardize, what they leave to you
- Feature freshness, backfills, and time-travel queries
- *Domain:* fraud features (velocity, aggregates over time windows); *Exercise:* design a feature pipeline + store schema for time-windowed fraud features; specify training/serving consistency guarantees

### Part 2 — The Modeling Layer (how the model is built)

**M7 · Experimentation & Reproducibility**
- *Core question:* How do we make model development an engineering discipline, not alchemy?
- Experiment tracking: params, metrics, artifacts, data/code versions
- Reproducibility = code + data + environment + seed
- The experiment as the unit of progress; comparing experiments fairly
- Failure mode: unreproducible results, "it worked on my machine"
- *Domain:* churn-prediction iterations; *Exercise:* specify the tracking schema + reproducibility checklist for a modeling team

**M8 · Training Infrastructure & Model Selection**
- *Core question:* What do we actually need to train, and how do we pick a model?
- Baselines first: heuristic, linear, prior model — complexity is a *budget*, not a default
- Training infra: single-node → GPU → distributed; cost vs time
- Model selection: capacity / data-size / latency / explainability lens; when simple wins
- Hyperparameter tuning & AutoML — when they help and when they're waste
- *Domain:* demand forecasting; *Exercise:* given a requirements table (data size, latency, cost, explainability), justify a model class + training infrastructure

**M9 · The Model Registry & Lifecycle**
- *Core question:* How does a model become a versioned, governable artifact?
- Model versioning, tagging, and staging (dev / staging / prod)
- The registry as the source of truth for "what's deployed"
- Model lineage: model → data → code → params
- Promotion & deprecation; retiring models safely
- *Domain:* multi-model fraud system; *Exercise:* design the registry + promotion policy for a team running 20+ model versions

### Part 3 — The Verification Layer (how we trust it)

**M10 · Offline Evaluation**
- *Core question:* How do we measure a model honestly before it ships?
- Metric selection beyond accuracy; imbalanced / ranking / precision-recall tradeoffs
- Splits done right: temporal, grouped, stratified — leakage-free validation
- Offline metrics as *proxies*; where they systematically mislead
- Evaluation on slices; per-cohort and fairness-aware evaluation
- *Domain:* claims triage (imbalanced); *Exercise:* design the metric suite + split strategy for an imbalanced triage model; list the leakage traps

**M11 · Online Evaluation, A/B Testing & Approval Gates**
- *Core question:* How do we know the model wins in production, and when do we let it in?
- The offline–online gap and its causes (feedback loops, drift, distribution shift)
- A/B testing: power, guardrails, ramp-up, holdout groups
- Interleaving & bandits (brief) for ranking systems
- Approval gates: what must be true to promote a model
- *Domain:* search ranking; *Exercise:* design an A/B rollout with guardrails + a promotion gate for a ranking change

### Part 4 — The Serving Layer (how it reaches users)

**M12 · Serving Architectures**
- *Core question:* How do predictions actually get delivered, and at what cost?
- Serving patterns: batch, online (REST/gRPC), streaming, embedded/edge
- Latency budgets and SLOs for serving
- Model serialization & runtimes (ONNX, TorchScript, SavedModel, ONNX Runtime, TensorRT)
- The serving architecture as a design surface, not an afterthought
- *Domain:* real-time credit scoring (200 ms budget); *Exercise:* choose and justify a serving architecture for a 200 ms fraud check; draw the data flow

**M13 · Deployment Strategies & CI/CD for ML**
- *Core question:* How do we ship a model safely, and roll it back when it breaks?
- Deployment strategies: shadow, canary, blue-green, A/B — and rollback
- ML CI/CD: data + code + model all trigger pipelines; retraining as CI
- Testing in ML: data tests, model tests, pipeline tests, serving smoke tests
- The promotion pipeline: staging → shadow → canary → prod
- *Domain:* recommender-system rollout; *Exercise:* design a CI/CD pipeline with canary + auto-rollback triggers for a recommender

**M14 · Scaling, Optimization & Cost**
- *Core question:* How do we serve more predictions, faster, cheaper — without degrading quality?
- Batching, caching, and memoization at inference
- Model optimization: quantization, distillation, pruning, compilation
- Autoscaling & capacity planning; GPU vs CPU economics
- Cost engineering: cost per prediction as a design metric
- *Domain:* high-volume content moderation; *Exercise:* take a serving system at 1k QPS and design its path to 100k QPS with a cost ceiling

### Part 5 — The Operational Layer (how we run it)

**M15 · Monitoring & Observability**
- *Core question:* When a production model degrades, how do we see it — and reconstruct why?
- Monitoring vs observability; the four pillars: system health, data quality, model performance, business impact
- Tracing a prediction: inputs → features → model → output → action
- Metrics that matter: latency percentiles, prediction volume, error rates, business KPI
- SLOs, alerting, and incident response for ML systems
- *Domain:* production fraud system; *Exercise:* design the trace schema + the 5 alerts a platform team should fire on

**M16 · Drift, Retraining & Feedback Loops**
- *Core question:* How does a model stay correct as the world changes?
- Data drift vs concept drift; detection (PSI, KL, statistical tests)
- Feedback loops: predictions changing the data they predict on
- Delayed labels & proxy metrics; when ground truth arrives late
- Retraining triggers & continuous training; the cost of too-frequent retraining
- *Domain:* dynamic pricing (strong feedback loop); *Exercise:* design drift detection + a retraining policy for a pricing model with delayed labels

**M17 · Governance, Security & Cost**
- *Core question:* Who decides what the system may do, and how is that enforced and audited?
- Model lineage & auditability; reproducing any production prediction
- Fairness & bias: measurement, mitigation, and the limits of both
- Security: adversarial inputs, data poisoning, model extraction — and defenses
- Compliance: regulated domains, retention, explainability, disclosure
- Cost governance: budgets, attribution, and killing models that don't pay
- *Domain:* lending (fairness + compliance); *Exercise:* design the governance envelope — lineage, fairness checks, audit — for a lending model

### Part 6 — Synthesis

**M18 · End-to-End Design (worked example)**
- *Core question:* How do all the layers compose into one coherent, defensible design?
- A complete worked example — a production fraud-detection system — designed layer by layer
- The design method: requirements → failure-mode analysis → layer decisions → ADRs → eval strategy → serving → monitoring
- Tradeoff tension points: freshness vs cost, accuracy vs latency, autonomy vs auditability
- What a senior engineer should *produce*: a design document a team could build from
- *Exercise:* take one of your own real problems and produce the first-draft design document using the course method

---

## 4. Writing conventions

- **Vividness:** narrative-driven lessons; each module opens with a concrete scenario, uses recurring characters/cases, and closes with the design exercise
- **Diagrams:** Mermaid for stack/layer/flow diagrams
- **Code:** vendor-neutral Python (sklearn, PyTorch, Pandera, MLflow, FastAPI, Docker, Prometheus/Grafana), API-level depth; inline snippets only where a concept needs them, full demos deferred to Pass 2 behind `💻 CODED DEMO (Pass 2)` placeholders
- **Callouts:** `Failure mode` (how this breaks), `Tradeoff` (decision ledger), `Reference stack at a glance` (the Python surface), `Design exercise` (end of module)
- **Grounding:** all tool-specific claims verified against the official docs of the reference stack (sklearn/PyTorch/MLflow/FastAPI/Pandera/etc.); sources cited
- **Versioning:** pin library minor versions used in examples; note upgrade caveats

## 5. Proposed repo structure

```
ML-Engineer/
├── syllabus.md              ← this blueprint (the map)
├── README.md                ← course landing page
├── modules/
│   ├── 01-what-is-an-ml-system/README.md
│   ├── ... (one folder per module; each may carry a code/ dir for its Pass-2 demos)
│   └── 18-end-to-end-design/README.md
└── tech/                    ← reference shelf: specs/requirements/setup per tool
    ├── airflow.md
    ├── kubeflow-pipelines.md
    ├── tfx.md
    ├── prefect.md
    └── alibi-detect.md
```

Each module is a single rich `README.md` (or split into chapters if it outgrows one file).

---

## 6. References

- [Chip Huyen — Designing Machine Learning Systems](https://www.oreilly.com/library/view/designing-machine-learning/9781098107956/) (O'Reilly)
- [Lakshmanan, Robinson, Munn — Machine Learning Design Patterns](https://www.oreilly.com/library/view/machine-learning-design/9781098115777/)
- [Sculley et al. — Hidden Technical Debt in Machine Learning Systems (NeurIPS 2015)](https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html)
- [Google — Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml)
- [Google — The ML Test Score](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/)
- [Breck et al. — Data Validation for Machine Learning (MLSys 2019)](https://mlsys.org/Conferences/2019/doc/2019/167.pdf)
- [Ameisen — Building Machine Learning Powered Applications](https://www.oreilly.com/library/view/building-machine-learning/9781492045106/)
- [Chip Huyen — blog (MLOps, real-time ML, evaluation)](https://huyenchip.com/blog/)
- Official docs of the reference stack: scikit-learn, PyTorch, MLflow, FastAPI, Pandera, Great Expectations, Prometheus, Grafana, alibi-detect (drift), Prefect (orchestration)

---

## 7. Decisions so far

- **Stack:** vendor-neutral Python — sklearn + PyTorch (modeling), Pandera/Great Expectations (validation), MLflow (tracking/registry), FastAPI + Docker (serving), Prometheus/Grafana (observability); Prefect (orchestration) + alibi-detect (drift) with code in Pass 2
- **Depth:** maximal 18-module structure; no time constraint
- **Format:** rich written Markdown lessons for professional self-study; no lab infrastructure yet
- **Code:** inline Python where a concept needs it; full coded demos deferred to Pass 2, captured as `💻 CODE (Pass 2)` work-order blockquotes (demonstrates / where / requirements / accept) in the module READMEs; module-level demo code lands in each module's `code/` folder
- **Tech shelf:** `tech/` holds per-tool reference docs (specs, versions, requirements, setup) for Prefect, alibi-detect, Airflow, Kubeflow Pipelines, TFX; the no-infra restriction is lifted for the orchestration modules (M13, M16)
- **Exercises:** design exercises (paper-based) end every module; labs deferred
- **Assessment:** deferred
- **Capstone:** folded into M18 as a worked example (not a graded project)
- **Examples:** domains vary per module; real-world + Python-native texture
- **Out of scope:** ML theory/math, novel model research, general software basics, pure infra beyond ML needs, frontend

## 8. Status — complete draft

**All 18 modules (M1–M18) are written** — each as a rich `README.md` in `modules/`, following the conventions in section 4 (core question, failure-mode/tradeoff/reference-stack callouts, Mermaid diagrams, inline Python + `💻 CODED DEMO (Pass 2)` placeholders, and a closing design exercise). The capstone decision for M18 remains deferred (see the `📌` note in that module). Full coded demos remain a second pass.
