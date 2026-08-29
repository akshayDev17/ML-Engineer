# alibi-detect — Tech Reference

> Reference doc for the ML Engineering Design course. Module lessons link here for specs; the demos that exercise alibi-detect live in the module `code/` folders (written in Pass 2). Runs locally — **no infra required**.

## What it is & when to reach for it

alibi-detect (Seldon) is a library of statistical and learned **drift detectors**: `KSDrift`, `ChiSquareDrift`, `MMDDrift`, `TabularDrift`, plus concept-drift detectors (`ClassifierDrift`, `ProphetDetector`). The API is detector-shaped — `fit` on a reference set, `predict` on new data, returning `is_drift` / `p_val` / `threshold` — which maps directly onto the drift-detection design in M16 and the monitoring pillars in M15. Free open source (Apache-2.0).

## Specs & versions

| Item | Value |
|---|---|
| License | Apache-2.0 |
| Pin | `alibi-detect==0.11.*` |
| API surface used | `alibi_detect.cd.KSDrift` (and siblings), `detector.fit/predict`, `preds["data"]` |

## Requirements

- `pip install alibi-detect` — that's it.

## Setup / run skeleton

1. `detector = KSDrift(x_ref, p_val=0.05)` — fit on the training reference
2. `pred = detector.predict(x_new)` — on each new window
3. Read `pred["data"]["is_drift"]` and `p_val` per feature → threshold → trigger

## Working code (Pass 2)

- `modules/16-drift-retraining/code/drift_detector.py` — KSDrift fit/predict, the library form of the inline PSI in M16
- `modules/15-monitoring-observability/code/drift_alerting.py` — detector p-values wired to Prometheus gauges + alert
- Full per-demo specs live in those modules' `💻 CODE (Pass 2)` blockquotes.

## Gotchas / failure modes

- Detectors are fit on the reference distribution — refit when the reference legitimately changes
- p-values on large data: a "significant" drift may be practically trivial — pair with effect size / PSI

## Sources

- alibi-detect official docs (`docs.seldon.io/projects/alibi-detect`)
