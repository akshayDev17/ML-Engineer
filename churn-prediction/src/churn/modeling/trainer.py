"""The training loop.

    for each epoch:
        train   — mini-batch AdamW on BCEWithLogits(pos_weight), gradient clipping
        validate— on the untouched validation split: unweighted BCE + PR-AUC + ROC-AUC
        publish — EpochLog to callbacks (early stopping, LR schedule, logging, pruning)

The validation set is used for *decisions about training* (when to stop, when to decay
the LR, which hyper-parameters win, which threshold to use) — never for gradient updates.
The test set is not visible to this module at all.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from churn.common.registry import Registry
from churn.config import TrainingConfig
from churn.modeling.callbacks import Callback, EpochLog, TrainingState

OPTIMIZERS: Registry[torch.optim.Optimizer] = Registry("optimizer")
OPTIMIZERS.register("adamw")(lambda params, lr, weight_decay: torch.optim.AdamW(params, lr=lr, weight_decay=weight_decay))
OPTIMIZERS.register("adam")(lambda params, lr, weight_decay: torch.optim.Adam(params, lr=lr, weight_decay=weight_decay))
OPTIMIZERS.register("sgd")(lambda params, lr, weight_decay: torch.optim.SGD(
    params, lr=lr, weight_decay=weight_decay, momentum=0.9, nesterov=True))


@dataclass(frozen=True)
class ArrayDataset:
    X: np.ndarray
    y: np.ndarray

    def tensors(self) -> tuple[torch.Tensor, torch.Tensor]:
        return torch.as_tensor(self.X, dtype=torch.float32), torch.as_tensor(self.y, dtype=torch.float32)


def make_train_loader(data: ArrayDataset, batch_size: int, seed: int,
                      sample_weights: np.ndarray | None = None) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    dataset = TensorDataset(*data.tensors())
    if sample_weights is not None:
        sampler = WeightedRandomSampler(torch.as_tensor(sample_weights, dtype=torch.double),
                                        num_samples=len(dataset), replacement=True, generator=generator)
        return DataLoader(dataset, batch_size=batch_size, sampler=sampler, drop_last=len(dataset) > batch_size)
    # drop_last avoids a size-1 final batch, which BatchNorm cannot normalise.
    return DataLoader(dataset, batch_size=batch_size, shuffle=True, generator=generator,
                      drop_last=len(dataset) > batch_size)


@torch.no_grad()
def predict_proba(model: nn.Module, X: np.ndarray, device: str = "cpu", batch_size: int = 4096) -> np.ndarray:
    model.eval()
    out = []
    for start in range(0, len(X), batch_size):
        xb = torch.as_tensor(X[start:start + batch_size], dtype=torch.float32, device=device)
        out.append(torch.sigmoid(model(xb)).cpu().numpy())
    return np.concatenate(out)


class Trainer:
    def __init__(self, model: nn.Module, config: TrainingConfig, callbacks: list[Callback] | None = None,
                 pos_weight: float = 1.0, device: str = "cpu", seed: int = 42) -> None:
        self._model = model.to(device)
        self._config = config
        self._callbacks: list[Callback] = list(callbacks or [])
        self._device = device
        self._seed = seed
        self._loss = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, device=device))
        self._val_loss = nn.BCEWithLogitsLoss()  # unweighted: measured at the real-world prior
        self.optimizer = OPTIMIZERS.create(config.optimizer, params=model.parameters(), lr=config.lr,
                                           weight_decay=config.weight_decay)

    def add_callbacks(self, *callbacks: Callback) -> "Trainer":
        """Subscribe observers (some, like the LR scheduler, need `self.optimizer` first)."""
        self._callbacks.extend(callbacks)
        return self

    def fit(self, train: ArrayDataset, val: ArrayDataset, sample_weights: np.ndarray | None = None) -> TrainingState:
        loader = make_train_loader(train, self._config.batch_size, self._seed, sample_weights)
        X_val, y_val = (t.to(self._device) for t in val.tensors())
        state = TrainingState(self._model, self.optimizer)
        for cb in self._callbacks:
            cb.on_train_begin(state)

        for epoch in range(1, self._config.max_epochs + 1):
            train_loss = self._train_one_epoch(loader)
            epoch_log = self._validate(epoch, train_loss, X_val, y_val)
            state.history.append(epoch_log)
            for cb in self._callbacks:
                cb.on_epoch_end(state, epoch_log)
            if state.stop_training:
                break

        for cb in self._callbacks:
            cb.on_train_end(state)
        return state

    def _train_one_epoch(self, loader: DataLoader) -> float:
        self._model.train()
        total, count = 0.0, 0
        for xb, yb in loader:
            xb, yb = xb.to(self._device), yb.to(self._device)
            self.optimizer.zero_grad(set_to_none=True)
            loss = self._loss(self._model(xb), yb)
            loss.backward()
            if self._config.grad_clip_norm:
                nn.utils.clip_grad_norm_(self._model.parameters(), self._config.grad_clip_norm)
            self.optimizer.step()
            total += loss.item() * len(yb)
            count += len(yb)
        return total / max(count, 1)

    @torch.no_grad()
    def _validate(self, epoch: int, train_loss: float, X_val: torch.Tensor, y_val: torch.Tensor) -> EpochLog:
        self._model.eval()
        logits = self._model(X_val)
        proba = torch.sigmoid(logits).cpu().numpy()
        y_true = y_val.cpu().numpy()
        return EpochLog(
            epoch=epoch,
            train_loss=train_loss,
            val_loss=self._val_loss(logits, y_val).item(),
            val_pr_auc=float(average_precision_score(y_true, proba)),
            val_roc_auc=float(roc_auc_score(y_true, proba)),
            lr=self.optimizer.param_groups[0]["lr"],
        )
