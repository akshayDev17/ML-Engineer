# M2 · ML Failure Science

> **Core question:** What does a production ML system actually do wrong, and why — before we design anything?

---

## The reflex you're building

Before you can design an ML system, you need to know how they die. 
- Not the dramatic deaths — the quiet ones, where a model that was fine on Tuesday is wrong on Thursday and nobody notices for a month. 
- Production ML doesn't usually fail with a crash; it fails with a slow, silent slide into wrongness.

This module is a taxonomy of those failures. 
- It's the most important module in Part 0, because every later module exists to prevent a specific entry in this list. 
- From here on, the reflex is: *when an ML system misbehaves, which failure class is this, and which layer should have caught it?*

## The six failure classes

### 1. Data leakage

Leakage is when your training data contains information that would not be available at prediction time. The model doesn't "cheat" — it just learns from a signal that won't exist in production, so its performance is a mirage.

Three common forms:

- **Target leakage** — a feature *is* the label, or is computed from it. Example: including "number of days since the customer churned" as a feature to predict churn. At prediction time you don't know that; in training you do.
- **Temporal leakage** — training on the future. A random train/test split on time-series data lets tomorrow's events leak into yesterday's training rows.
- **Validation leakage** — preprocessing (scaling, imputation, feature selection) fitted on the whole dataset including the test set, or a test set that overlaps the training set through near-duplicate rows.

> **⚠️ Failure mode** — *The leakage mirage.* Leakage inflates offline metrics and produces a model that is *correctly learning the wrong thing*. It is the single most common reason a "great" model fails in production, and it's invisible unless you audit *where every feature came from and when*.

### 2. Training–serving skew

The features the model was trained on and the features it receives at inference are computed *differently*. Same feature name, different meaning — or worse, a feature silently missing or reordered.

Skew is insidious because the model doesn't error out. It just receives slightly wrong inputs and produces confidently wrong outputs.

- **Code skew** — two implementations of the same feature (one in training, one in serving) that drift apart.
- **Data skew** — the serving data is drawn from a different population or window than training.
- **Silent feature dropout** — a feature is absent at serving time, and the serving code fills it with a default (often `0` or the mean) without telling anyone.

### 3. Drift (data and concept)

The world changes, and the model doesn't.

- **Data drift** — the *input* distribution changes. New device types, new user demographics, a new market. The model is now extrapolating into a region it never saw.
- **Concept drift** — the *relationship* between inputs and labels changes. The same transaction that was safe last year is fraud now, because fraudsters adapted. Same inputs, different correct answer.

Drift is a *fact of life*, not a bug. The design question is never "how do we prevent drift" — it's "how do we *detect* it and decide when to retrain."

### 4. Feedback loops

The model's predictions change the world, and the changed world changes the model's predictions. The loop can be **self-reinforcing** (runaway) or **self-defeating** (the model undermines its own signal).

- A pricing model that always matches the lowest competitor price trains on prices it itself set, then learns to set them lower.
- A fraud model that blocks transactions on certain channels reduces fraud *on those channels* — so the model sees less fraud there, concludes the channel is safe, and relaxes, letting fraud back in.
- A recommender that only ever shows a narrow band of content trains on its own narrow output and never discovers anything else (the "filter bubble" as a feedback loop).

Feedback loops are why "the model is stable" is not evidence the model is correct — it may be stable *because* it's closed itself off from the truth.

### 5. Silent degradation

The model gets worse and no one notices. This isn't a separate physical process so much as the *consequence* of the previous four going undetected: there's no measurement, so degradation is invisible.

Silent degradation is the scariest failure because it's not an event — it's an absence. The system was designed to *predict*, but not to *know whether its predictions are still right*. (M15–M16 are the entire cure.)

### 6. Cascading failure

An ML system depends on upstream systems — a data feed, a feature computation job, an external API. When one of those silently changes (an upstream schema change, a feed that goes stale, an API that starts returning errors), the ML system fails in a way no one anticipated, because the dependency was never treated as a first-class part of the design.

Cascading failure is the argument for **seams**: explicit, versioned contracts between layers, so a change upstream is *detected* rather than *absorbed silently*.

## Failure attribution: "the model" is rarely the culprit

Here is the single most useful mental move in this course:

> **"The model got worse" is almost always "the system around the model changed."**

A trained model is *frozen* — its weights don't drift on their own. When performance decays, the model hasn't changed; its **inputs** changed (drift, skew, a broken feed), or its **labels** changed (concept drift), or its **own predictions** changed the world (feedback). The model is the innocent party; the system failed it.

This matters because it tells you where to look. When an ML system degrades, do not retrain first. **Diagnose first.** Retraining a model against a world that has shifted just bakes in the shift — and if the real problem is a broken upstream feed, retraining won't fix it at all; it'll silently train on garbage.

> **⚖️ Tradeoff** — *Retrain vs. diagnose.* Retraining is the default reflex and often the wrong one. It's cheap to trigger and expensive in opportunity cost: while you retrain, the root cause (a skewed feature, a stale feed) persists. The ledger entry: *chose diagnosis-first, gave up the quick feeling of action, gained the actual fix.*

## The failure-class → layer map

This table is the through-line of the course. It maps each failure class to the layer that should have caught it — and each layer is a module. You'll see this mapping referenced (implicitly or explicitly) in every module from M4 on.

| Failure class | The layer that should have caught it | Module |
|---|---|---|
| Target / temporal / validation leakage | Data & feature pipelines; evaluation | M4, M6, M10 |
| Training–serving skew | Feature pipelines; serving | M6, M12 |
| Data / concept drift | Monitoring & observability | M15, M16 |
| Feedback loops | Evaluation (online); monitoring | M11, M16 |
| Silent degradation | Monitoring & observability | M15 |
| Cascading failure | Architecture (seams, contracts) | M3 |
| Unreproducible results | Experimentation & tracking | M7 |
| Bad offline → online transfer | Evaluation (online) | M11 |
| Unfair / non-compliant outcomes | Governance | M17 |
| Unsafe / unbounded deployment | Serving & CI/CD | M13 |

Notice how the *same* failure can be caught at multiple layers — that's defense in depth, and we'll design for it deliberately rather than hoping.

## Three real postmortems

Real failures, with the failure class named. Read these as case studies you'll return to.

### Zillow Offers (2021) — feedback loop + over-automation

Zillow's home-buying ("iBuying") business used an ML model to price homes it would buy and resell. The model systematically overpredicted values, Zillow overpaid, and in late 2021 it shut the division down with losses in the hundreds of millions.

The failure wasn't one bug — it was a **feedback loop** compounded by human override being removed. Aggressive bidding pushed prices up, which fed the model's own inflated estimates back as "market data," which justified more aggressive bidding. The system amplified its own error until it was unsustainable.

*Failure classes: feedback loop, silent degradation (until it was too late), and a governance gap (the human-in-the-loop override was disabled).*

### Epic Sepsis Model (2021) — training–serving skew

A widely deployed sepsis-prediction model was externally validated and found to miss roughly two-thirds of sepsis cases while raising false alarms. The root cause, per the validation study: the model used features that were **not available at prediction time** — the training data contained information (like certain lab values and timing signals) that, in a real hospital, arrives *after* the point where you'd need the prediction.

This is training–serving skew of the nastiest kind: the model was trained on a world where it "knew" things it could not know in production.

*Failure classes: training–serving skew (specifically, target/temporal leakage into features).*

### Google Flu Trends (2014) — concept drift + feedback loop

Google Flu Trends predicted flu prevalence from search queries. It worked beautifully for a while, then dramatically overestimated flu for years. Why? Search behavior changed (concept drift — the query-to-flu relationship shifted), and media coverage of the model's own predictions changed how people searched (a feedback loop through the very thing being measured).

*Failure classes: concept drift, feedback loop, and a lack of monitoring that let both run undetected.*

> **⚠️ Failure mode** — *The postmortem pattern.* In all three cases, the model was not the villain. The villain was an unmanaged system property: a feedback loop, a skew, a drift. When you read an ML failure story, train yourself to ask not "what was the bug?" but "which layer failed, and what design decision would have caught it?"

> **🐍 Reference stack at a glance** — None yet, deliberately. Failure science is a taxonomy you carry in your head, not a library you import. The tools that *detect* each failure class arrive with the layers that own them: Pandera/Great Expectations for skew and leakage (M5, M6), MLflow for unreproducible results (M7), Prometheus + Evidently for drift and silent degradation (M15, M16). For now, the stack *is* the failure taxonomy itself.

## Where code is needed

Failure science is conceptual, but a few of these failures are *only* believable when you've seen them happen in numbers. Two demos are deferred:

> **💻 CODED DEMO (Pass 2)** — *Leakage in action:* the same model trained with a leaky feature vs. a clean one, side by side, showing the inflated metric and the collapse in production. This is the course's most important "aha," so it gets a full demo.

> **💻 CODED DEMO (Pass 2)** — *Drift made visible:* a synthetic stream where the input distribution shifts, and the model's accuracy decays while its *confidence stays flat* — the visual essence of silent degradation.

## Design exercise

Pick three ML failure stories you know (from the news, your own work, or the postmortems above). For each:

1. **Classify it** — name the primary failure class (or classes) using the taxonomy.
2. **Attribute it** — the model didn't change; what in the *system* changed? (A feed? A label source? The world? Its own predictions?)
3. **Locate it** — using the failure-class → layer map, name the layer that *should* have caught it, and the module where you'd find that layer.
4. **The ledger** — write one line: *what they chose (implicitly), and what it cost them.*

The goal is fluency: by the end of this course, "an ML system failed" should instantly decompose into *failure class → system change → responsible layer → missing design decision*. That decomposition *is* ML engineering design.

---

*Next: M3 · ML System Architecture & the Reference Stack — the layer diagram in detail, seams, and ADRs, plus the Python stack we'll use throughout.*
