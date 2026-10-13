"""ADVANCED: Bayesian hyper-parameter optimisation with Optuna.

* Sampler — TPE (Tree-structured Parzen Estimator), `multivariate=True` so correlated
  parameters (lr <-> batch size, depth <-> dropout) are modelled jointly, seeded for
  reproducibility.
* Pruner — MedianPruner: a trial whose validation PR-AUC at epoch t is below the median of
  earlier trials at epoch t is stopped early (6 of 30 on the default run), so hopeless
  configurations stop wasting epochs; 30 trials take under a minute on a laptop CPU.
* Objective — best validation PR-AUC of the trial (threshold-free and imbalance-aware).
* The test split is never visible here; the winner is re-trained once and only then
  scored on test, so the reported test numbers are not tuned on.
"""
from __future__ import annotations

import optuna
import pandas as pd

from churn.common.logging import get_logger
from churn.modeling.callbacks import Callback
from churn.modeling.service import ModelSpec
from churn.tuning.base import TUNERS, HyperparameterTuner, TuningResult

log = get_logger(__name__)


class OptunaPruningCallback(Callback):
    """Bridge between our Observer-based trainer and Optuna's pruning protocol."""

    def __init__(self, trial: optuna.Trial, monitor: str) -> None:
        self._trial, self._monitor = trial, monitor

    def on_epoch_end(self, state, epoch_log):
        self._trial.report(epoch_log.metric(self._monitor), step=epoch_log.epoch)
        if self._trial.should_prune():
            raise optuna.TrialPruned(f"pruned at epoch {epoch_log.epoch}")


class SearchSpace:
    """What is tuned, and over which ranges. Every bound can be overridden from the YAML."""

    DEFAULTS = {
        "architecture": ["mlp", "residual_mlp"],
        "n_layers": [1, 3],
        "width": [32, 64, 128, 256],
        "dropout": [0.0, 0.5],
        "activation": ["relu", "gelu", "silu"],
        "batch_norm": [True, False],
        "lr": [1e-4, 1e-2],
        "weight_decay": [1e-6, 1e-2],
        "batch_size": [128, 256, 512],
    }

    def __init__(self, overrides: dict | None = None) -> None:
        self._space = {**self.DEFAULTS, **(overrides or {})}

    def suggest(self, trial: optuna.Trial, base: ModelSpec, max_epochs: int) -> ModelSpec:
        s = self._space
        n_layers = trial.suggest_int("n_layers", *s["n_layers"])
        width = trial.suggest_categorical("width", s["width"])
        architecture = {
            "name": trial.suggest_categorical("architecture", s["architecture"]),
            "hidden_dims": tuple(max(width // 2 ** i, 8) for i in range(n_layers)),  # funnel
            "dropout": trial.suggest_float("dropout", *s["dropout"]),
            "activation": trial.suggest_categorical("activation", s["activation"]),
            "batch_norm": trial.suggest_categorical("batch_norm", s["batch_norm"]),
        }
        training = {
            "lr": trial.suggest_float("lr", *s["lr"], log=True),
            "weight_decay": trial.suggest_float("weight_decay", *s["weight_decay"], log=True),
            "batch_size": trial.suggest_categorical("batch_size", s["batch_size"]),
            "max_epochs": max_epochs,
        }
        return base.with_overrides(architecture, training)


@TUNERS.register("optuna")
class OptunaTuner(HyperparameterTuner):
    def __init__(self, n_trials: int = 30, timeout_s: int | None = 900, max_epochs_per_trial: int = 40,
                 n_startup_trials: int = 8, n_warmup_steps: int = 8, seed: int = 42,
                 search_space: dict | None = None, storage: str | None = None, **_) -> None:
        self._n_trials = n_trials
        self._timeout = timeout_s
        self._max_epochs = max_epochs_per_trial
        self._n_startup, self._n_warmup = n_startup_trials, n_warmup_steps
        self._seed = seed
        self._space = SearchSpace(search_space)
        self._storage = storage

    def tune(self, base, data, service):
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(
            direction="minimize" if base.training.monitor.endswith("loss") else "maximize",
            sampler=optuna.samplers.TPESampler(seed=self._seed, multivariate=True, n_startup_trials=self._n_startup),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=self._n_startup, n_warmup_steps=self._n_warmup),
            storage=self._storage, study_name="churn-mlp", load_if_exists=self._storage is not None,
        )

        def objective(trial: optuna.Trial) -> float:
            spec = self._space.suggest(trial, base, self._max_epochs)
            _, state = service.train(spec, data, extra_callbacks=[OptunaPruningCallback(trial, base.training.monitor)],
                                     verbose=False)
            best = max(state.history, key=lambda e: e.metric(base.training.monitor))
            trial.set_user_attr("best_epoch", best.epoch)
            return best.metric(base.training.monitor)

        def log_trial(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
            value = "pruned" if trial.state == optuna.trial.TrialState.PRUNED else f"{trial.value:.4f}"
            log.info("trial %2d %-7s best so far %.4f | %s", trial.number, value, study.best_value,
                     {k: (round(v, 6) if isinstance(v, float) else v) for k, v in trial.params.items()})

        study.optimize(objective, n_trials=self._n_trials, timeout=self._timeout, callbacks=[log_trial])

        p = study.best_params
        best_spec = base.with_overrides(
            architecture={"name": p["architecture"], "dropout": p["dropout"], "activation": p["activation"],
                          "batch_norm": p["batch_norm"],
                          "hidden_dims": tuple(max(p["width"] // 2 ** i, 8) for i in range(p["n_layers"]))},
            training={"lr": p["lr"], "weight_decay": p["weight_decay"], "batch_size": p["batch_size"]},
        )
        trials: pd.DataFrame = study.trials_dataframe()
        n_pruned = int((trials["state"] == "PRUNED").sum())
        return TuningResult(best_spec, study.best_value, trials,
                            f"Optuna TPE+MedianPruner: {len(trials)} trials ({n_pruned} pruned), "
                            f"best val {base.training.monitor}={study.best_value:.4f}")
