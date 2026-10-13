"""Facade that turns a `ModelSpec` + prepared arrays into a trained network.

Both the final training run and every Optuna trial go through `ModelTrainingService.train`,
so "how a model is trained" exists exactly once.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from churn.common.reproducibility import seed_everything
from churn.config import ArchitectureConfig, TrainingConfig
from churn.modeling.callbacks import Callback, EarlyStopping, ProgressLogger, ReduceLROnPlateauCallback, TrainingState
from churn.modeling.networks import NETWORKS, ChurnNetwork
from churn.modeling.trainer import ArrayDataset, Trainer


@dataclass(frozen=True)
class ModelSpec:
    architecture: ArchitectureConfig
    training: TrainingConfig

    def with_overrides(self, architecture: dict | None = None, training: dict | None = None) -> "ModelSpec":
        return ModelSpec(replace(self.architecture, **(architecture or {})),
                         replace(self.training, **(training or {})))


@dataclass(frozen=True)
class TrainingData:
    train: ArrayDataset
    val: ArrayDataset
    pos_weight: float = 1.0
    sample_weights: np.ndarray | None = None
    effective_positive_rate: float = 0.5

    @property
    def input_dim(self) -> int:
        return self.train.X.shape[1]


class ModelTrainingService:
    def __init__(self, device: str = "cpu", seed: int = 42) -> None:
        self._device = device
        self._seed = seed

    def build_network(self, spec: ModelSpec, input_dim: int) -> ChurnNetwork:
        return NETWORKS.create(spec.architecture.name, input_dim=input_dim, arch=spec.architecture)

    def train(self, spec: ModelSpec, data: TrainingData, extra_callbacks: list[Callback] | None = None,
              verbose: bool = True) -> tuple[ChurnNetwork, TrainingState]:
        seed_everything(self._seed)
        model = self.build_network(spec, data.input_dim)
        model.init_output_bias(data.effective_positive_rate)
        cfg = spec.training
        mode = "min" if cfg.monitor.endswith("loss") else "max"
        trainer = Trainer(model, cfg, pos_weight=data.pos_weight, device=self._device, seed=self._seed)
        trainer.add_callbacks(
            ReduceLROnPlateauCallback(trainer.optimizer, cfg.monitor, mode, cfg.lr_scheduler_factor,
                                      cfg.lr_scheduler_patience),
            EarlyStopping(cfg.monitor, mode, cfg.early_stopping_patience),
            *(extra_callbacks or []),
            *([ProgressLogger()] if verbose else []),
        )
        state = trainer.fit(data.train, data.val, data.sample_weights)
        return model, state
