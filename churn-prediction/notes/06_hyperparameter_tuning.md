# 06 · Hyper-parameter tuning (advanced deep-dive)

## Library: **Optuna**

| need | Optuna | alternatives considered |
|---|---|---|
| smarter than grid/random on a budget | TPE (Bayesian, sequential) | `GridSearchCV` (the notebooks): exponential in the number of parameters and blind to past results; random search: fine, but no learning |
| stop bad trials early | first-class **pruners** with per-epoch `trial.report()` | Hyperopt: no pruning; scikit-optimize: unmaintained |
| *conditional* search spaces (depth → widths, architecture-specific params) | define-by-run: the space is plain Python | Ray Tune / Keras Tuner: also capable, but a cluster runtime (Ray) or a framework lock-in (Keras) is overkill for one CPU |
| fits a PyTorch loop we already own | no wrapper class needed; one callback | Lightning/Ray integrations assume their own trainer |
| reproducible and resumable | seeded sampler; optional SQLite `storage` | — |

## What is tuned (`tuning/optuna_tuner.SearchSpace`)

| hyper-parameter | range | why it is worth tuning |
|---|---|---|
| `architecture` | {`mlp`, `residual_mlp`} | the inductive bias; shown here as a polymorphic swap |
| `n_layers` | 1 – 3 | capacity / depth |
| `width` | {32, 64, 128, 256}; layer *i* = width / 2^i (a funnel) | capacity / breadth |
| `dropout` | 0.0 – 0.5 | regularisation (interacts with width) |
| `activation` | {relu, gelu, silu} | smoothness of the decision surface |
| `batch_norm` | {on, off} | optimisation stability vs noise |
| `lr` | 1e-4 – 1e-2 (log) | the single most sensitive parameter |
| `weight_decay` | 1e-6 – 1e-2 (log) | regularisation |
| `batch_size` | {128, 256, 512} | gradient noise; minority examples per batch |

**Deliberately *not* tuned:**
- **Early-stopping patience and max epochs.** Early stopping already adapts the training length per trial.
- **The decision threshold.** It's a business choice made after training (`notes/07`).
- **`pos_weight`.** It interacts with the threshold rather than with ranking quality (`notes/04`).
- **The optimizer.** AdamW, with lr and weight decay tuned.

## The code (abridged from `src/churn/tuning/optuna_tuner.py`)

```python
study = optuna.create_study(
    direction="maximize",                                        # validation PR-AUC
    sampler=optuna.samplers.TPESampler(seed=42, multivariate=True, n_startup_trials=8),
    pruner=optuna.pruners.MedianPruner(n_startup_trials=8, n_warmup_steps=8),
)

def objective(trial: optuna.Trial) -> float:
    n_layers = trial.suggest_int("n_layers", 1, 3)
    width    = trial.suggest_categorical("width", [32, 64, 128, 256])
    spec = base_spec.with_overrides(
        architecture={"name": trial.suggest_categorical("architecture", ["mlp", "residual_mlp"]),
                      "hidden_dims": tuple(max(width // 2**i, 8) for i in range(n_layers)),
                      "dropout": trial.suggest_float("dropout", 0.0, 0.5),
                      "activation": trial.suggest_categorical("activation", ["relu", "gelu", "silu"]),
                      "batch_norm": trial.suggest_categorical("batch_norm", [True, False])},
        training={"lr": trial.suggest_float("lr", 1e-4, 1e-2, log=True),
                  "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
                  "batch_size": trial.suggest_categorical("batch_size", [128, 256, 512]),
                  "max_epochs": 40})
    # the SAME training service as the final fit; the pruning callback reports val PR-AUC each epoch
    _, state = service.train(spec, data, extra_callbacks=[OptunaPruningCallback(trial, "val_pr_auc")])
    return max(e.val_pr_auc for e in state.history)

study.optimize(objective, n_trials=30, timeout=900)
best_spec = ...  # rebuilt from study.best_params, then retrained ONCE with full max_epochs
```

`OptunaPruningCallback` is an **Adapter** between the trainer's Observer protocol and Optuna's `report` / `should_prune` protocol, so the training loop knows nothing about Optuna.

## Result on the default run

- 30 trials in about 45 seconds on CPU, **6 pruned**.
- Best validation PR-AUC was **0.4325**: MLP [64, 32], SiLU, no BatchNorm, dropout 0.03, lr 3.5e-3, weight decay 8.9e-4, batch 512. The best `residual_mlp` reached 0.4284.
- **Test after tuning: ROC-AUC 0.819 and PR-AUC 0.424, versus 0.822 / 0.423 with the hand-picked values.**

**Honest reading:** tuning bought nothing measurable on test. The spread between trials (0.41–0.43 validation PR-AUC) is about the size of the validation noise with ≈ 290 positives, and the model is already near the data's ceiling (oracle ROC-AUC 0.859, `notes/01`). This is the M8 lesson in miniature: *tuning matters at the margin, after the design is right.* The feature, imbalance, and threshold decisions moved the metrics far more than any hyper-parameter did.

## Guarding against overfitting the validation set

- The test split never enters the study.
- With many trials and a small validation set, the "best" trial is partly a lucky draw (winner's curse). Mitigations, in order of cost:
  1. keep the search space small and sensible (done);
  2. re-train the top-k configurations with different seeds and pick the most *stable* one;
  3. use **nested CV**: an inner CV objective for Optuna and an outer fold for the estimate.
