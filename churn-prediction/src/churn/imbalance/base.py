"""Class-imbalance handling strategies.

Every strategy receives the *sanitized training split only* (imputed, not yet one-hot) and
returns a `BalancedTrainingSet` that tells the trainer how to compensate — by changing the
rows (resampling), the loss (pos_weight), or the batch composition (sample weights).
Validation and test sets are never rebalanced: they must reflect the real-world prior,
otherwise precision, PR-AUC and the chosen threshold would all be fiction.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd

from churn.common.registry import Registry

IMBALANCE_STRATEGIES: Registry["ImbalanceStrategy"] = Registry("imbalance strategy")


@dataclass
class BalancedTrainingSet:
    X: pd.DataFrame
    y: pd.Series
    pos_weight: float = 1.0  # multiplies the positive-class term of BCEWithLogitsLoss
    sample_weights: np.ndarray | None = None  # drives a WeightedRandomSampler when set
    description: str = ""

    @property
    def positive_rate(self) -> float:
        return float(np.mean(self.y))

    @property
    def effective_positive_rate(self) -> float:
        """The class prior the *loss* actually sees (used to initialise the output bias)."""
        y = np.asarray(self.y, dtype=float)
        if self.sample_weights is not None:
            return float(np.average(y, weights=self.sample_weights))
        p = y.mean()
        return float(self.pos_weight * p / (self.pos_weight * p + (1 - p)))


class ImbalanceStrategy(ABC):
    @abstractmethod
    def prepare(self, X: pd.DataFrame, y: pd.Series, categorical_columns: list[str]) -> BalancedTrainingSet: ...

    @staticmethod
    def _counts(y: pd.Series) -> tuple[int, int]:
        n_pos = int((y == 1).sum())
        return len(y) - n_pos, n_pos
