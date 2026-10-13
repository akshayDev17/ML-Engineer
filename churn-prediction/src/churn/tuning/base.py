"""Hyper-parameter tuning strategies (vanilla: fixed values; advanced: Optuna)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from churn.common.registry import Registry
from churn.modeling.service import ModelSpec, ModelTrainingService, TrainingData

TUNERS: Registry["HyperparameterTuner"] = Registry("tuner")


@dataclass
class TuningResult:
    spec: ModelSpec
    best_val_score: float | None = None
    trials: pd.DataFrame | None = None
    description: str = ""


class HyperparameterTuner(ABC):
    @abstractmethod
    def tune(self, base: ModelSpec, data: TrainingData, service: ModelTrainingService) -> TuningResult: ...
