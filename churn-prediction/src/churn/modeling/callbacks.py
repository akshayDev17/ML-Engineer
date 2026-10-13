"""Training callbacks (Observer pattern).

The trainer publishes lifecycle events; callbacks subscribe to the ones they care about.
Early stopping, LR scheduling, logging and Optuna pruning are therefore independent,
individually testable classes, and the training loop itself never changes when a new
behaviour is added (Open/Closed). Hooks are no-ops by default so each callback overrides
only what it needs (Interface Segregation).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import torch

from churn.common.logging import get_logger

log = get_logger(__name__)


@dataclass
class EpochLog:
    epoch: int
    train_loss: float
    val_loss: float
    val_pr_auc: float
    val_roc_auc: float
    lr: float

    def metric(self, name: str) -> float:
        return getattr(self, name)


@dataclass
class TrainingState:
    model: torch.nn.Module
    optimizer: torch.optim.Optimizer
    history: list[EpochLog] = field(default_factory=list)
    stop_training: bool = False
    stop_reason: str = ""


class Callback:
    def on_train_begin(self, state: TrainingState) -> None: ...

    def on_epoch_end(self, state: TrainingState, epoch_log: EpochLog) -> None: ...

    def on_train_end(self, state: TrainingState) -> None: ...


def _improved(value: float, best: float | None, mode: str, min_delta: float) -> bool:
    if best is None:
        return True
    return value > best + min_delta if mode == "max" else value < best - min_delta


class EarlyStopping(Callback):
    """Stop when the monitored *validation* metric hasn't improved for `patience` epochs and
    restore the best weights — the val set is what decides how long we train."""

    def __init__(self, monitor: str = "val_pr_auc", mode: str = "max", patience: int = 10,
                 min_delta: float = 1e-4) -> None:
        self.monitor, self.mode, self.patience, self.min_delta = monitor, mode, patience, min_delta
        self.best: float | None = None
        self.best_epoch: int = 0
        self._best_state: dict | None = None
        self._wait = 0

    def on_epoch_end(self, state, epoch_log):
        value = epoch_log.metric(self.monitor)
        if _improved(value, self.best, self.mode, self.min_delta):
            self.best, self.best_epoch, self._wait = value, epoch_log.epoch, 0
            self._best_state = copy.deepcopy(state.model.state_dict())
        else:
            self._wait += 1
            if self._wait >= self.patience:
                state.stop_training = True
                state.stop_reason = (f"early stop: {self.monitor} no better than {self.best:.4f} "
                                     f"(epoch {self.best_epoch}) for {self.patience} epochs")

    def on_train_end(self, state):
        if self._best_state is not None:
            state.model.load_state_dict(self._best_state)


class ReduceLROnPlateauCallback(Callback):
    def __init__(self, optimizer: torch.optim.Optimizer, monitor: str, mode: str, factor: float,
                 patience: int) -> None:
        self.monitor = monitor
        self._scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode=mode, factor=factor, patience=patience, min_lr=1e-6)

    def on_epoch_end(self, state, epoch_log):
        self._scheduler.step(epoch_log.metric(self.monitor))


class ProgressLogger(Callback):
    def __init__(self, every: int = 5) -> None:
        self.every = every

    def on_epoch_end(self, state, e):
        if e.epoch == 1 or e.epoch % self.every == 0:
            log.info("epoch %3d | train_loss %.4f | val_loss %.4f | val_pr_auc %.4f | val_roc_auc %.4f | lr %.2e",
                     e.epoch, e.train_loss, e.val_loss, e.val_pr_auc, e.val_roc_auc, e.lr)

    def on_train_end(self, state):
        if state.stop_reason:
            log.info(state.stop_reason)
