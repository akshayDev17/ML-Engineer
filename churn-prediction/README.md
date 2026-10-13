# Churn prediction: from dirty data to a servable PyTorch model

An end-to-end, leakage-aware churn pipeline:

1. synthetic **dirty** data → cleaning → feature selection
2. class-imbalance handling → a **PyTorch** MLP (with optional Optuna tuning)
3. test-set evaluation → a versioned, **ONNX-exportable** model bundle plus a FastAPI endpoint

It's built as a modular, SOLID, pattern-driven Python package. Every "advanced" deep-dive can be swapped with its vanilla counterpart by changing **config only**.

Background material: the course modules in [`../modules`](../modules) (M4–M12 especially) and the notebooks in `Machine-Learning-Concepts/src`. See [notes/10](notes/10_notebook_errata.md) for what was reused from them and what was corrected.

## Quick start

```bash
cd churn-prediction
uv venv .venv && uv pip install --python .venv/bin/python -e ".[serve,dev]"

.venv/bin/python -m churn                                   # defaults: 20,000 rows, imbalance ratio 9 (10% churn)
.venv/bin/python -m churn --n-rows 50000 --imbalance-ratio 19   # 5% churn

CHURN_CONFIG=configs/vanilla.yaml .venv/bin/python -m churn # vanilla profile (negative control)
.venv/bin/python -m pytest                                  # 36 tests, ~15 s
.venv/bin/python scripts/compare_strategies.py              # ablations -> notes/results/ablation.md (~3 min)
```

The command line takes **only** `--n-rows` (default 20,000) and `--imbalance-ratio` (majority:minority, default 9). Strategy choices come from the YAML profile (`CHURN_CONFIG`, default `configs/advanced.yaml`).

## Results (default run, held-out test split)

| precision | recall | F1 | ROC-AUC | PR-AUC (no-skill) | threshold |
|---:|---:|---:|---:|---:|---:|
| 0.412 | 0.459 | 0.434 | 0.819 | 0.424 (0.098) | 0.705 (chosen on val) |

The oracle ceiling (the generator's true probabilities) is ROC-AUC 0.859 / PR-AUC 0.489. On the vanilla profile, where the data has no pattern, the same pipeline correctly reports chance level (ROC-AUC 0.48–0.49 across runs). Figures and the full report are in `artifacts/registry/churn-model/v<N>/`.

## How the brief maps to the code

| requirement | where | notes |
|---|---|---|
| dummy churn data with the 6 given columns + 15 extra, of mixed types (`contract_type` nominal) | `data/schema.py`, `data/generators/` | [01](notes/01_data_generation.md) |
| ↳ *advanced:* data generated from an assumed pattern | `PatternChurnDataGenerator` (vanilla: `RandomChurnDataGenerator`) | [01](notes/01_data_generation.md) |
| dirty data needing real cleanup, preprocessing, and scaling | `data/corruption.py`, `data/cleaning.py`, `features/preprocessing.py` | [02](notes/02_dirty_data_and_cleaning.md) |
| feature selection + **lead-DS reasoning** | `features/selection/` | **[03](notes/03_feature_selection.md)** |
| imbalanced data, then "balancify" it | `--imbalance-ratio`, `imbalance/` | [04](notes/04_class_imbalance.md) |
| train/val/test split, PyTorch net, training, hyper-parameters, use of the val set | `data/splitting.py`, `modeling/` | [05](notes/05_training_and_hyperparameters.md) |
| ↳ *advanced:* tuning library, which hyper-parameters, code | `tuning/optuna_tuner.py` (vanilla: `tuning/fixed.py`) | [06](notes/06_hyperparameter_tuning.md) |
| precision, recall, F1, ROC-AUC curve on test | `evaluation/` | [07](notes/07_evaluation.md) |
| saving the model for serving | `serving/` | [08](notes/08_model_serving.md) |
| SOLID, design patterns, OOP | whole package | [09](notes/09_design_and_oop.md) |

## Vanilla ↔ advanced

| step | vanilla (`configs/vanilla.yaml`) | advanced (`configs/advanced.yaml`, default) |
|---|---|---|
| `data.generator` | `random`: no pattern, a negative control | `pattern`: latent-factor causal story |
| `imbalance.strategy` | `none` | `class_weight` (or `smotenc`, `weighted_sampler`, `random_undersample`) |
| `tuning.strategy` | `fixed` | `optuna` (TPE + median pruning) |
| `threshold.policy` | `fixed` 0.5 | `max_fbeta` (or `min_recall`) |

The core steps (cleaning, preprocessing, feature selection, stratified split, early stopping on validation, evaluation, packaging) are identical in both profiles. Any single line can be flipped on its own.

## Layout

```
churn-prediction/
├── configs/            advanced.yaml · vanilla.yaml
├── notes/              01–10 design notes · results/ablation.md
├── scripts/            compare_strategies.py (ablation study)
├── src/churn/          cli · config · factory (composition root) · pipeline
│   ├── common/         registry · reproducibility · logging
│   ├── data/           schema · generators/ · corruption · cleaning · splitting · repository
│   ├── features/       engineering · transformers · preprocessing · selection/
│   ├── imbalance/      strategies
│   ├── modeling/       networks · trainer · callbacks · service
│   ├── tuning/         fixed · optuna_tuner
│   ├── evaluation/     metrics · thresholds · plots
│   └── serving/        exporters · bundle · predictor · app (FastAPI)
└── tests/              config/CLI · data · features · modeling · end-to-end (incl. serving parity + HTTP)
```

`data/` (raw, cleaned, and ground-truth CSVs) and `artifacts/` (the model registry) are generated and git-ignored. One reference copy is force-committed: the three CSVs in `data/` and `artifacts/registry/churn-model/v1/model.onnx`, i.e. the default `python -m churn` run (advanced profile) whose results are quoted above. Re-running the pipeline overwrites them locally; restore with `git checkout -- data artifacts`.
