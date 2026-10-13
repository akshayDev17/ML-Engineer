"""Concrete imbalance strategies (vanilla: `none`; advanced: everything else)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE, SMOTENC
from imblearn.under_sampling import RandomUnderSampler

from churn.imbalance.base import IMBALANCE_STRATEGIES, BalancedTrainingSet, ImbalanceStrategy


@IMBALANCE_STRATEGIES.register("none")
class NoBalancing(ImbalanceStrategy):
    """VANILLA: train on the natural class prior with an unweighted loss."""

    def __init__(self, **_) -> None:
        pass

    def prepare(self, X, y, categorical_columns):
        return BalancedTrainingSet(X, y, description="natural prior, unweighted loss")


@IMBALANCE_STRATEGIES.register("class_weight")
class ClassWeighting(ImbalanceStrategy):
    """Cost-sensitive learning: up-weight the positive term of the loss by (n_neg/n_pos)^power.

    No rows are invented or thrown away, so it cannot overfit to synthetic points or lose
    majority-class information; power < 1 softens the weight when full re-weighting makes
    the model too trigger-happy.
    """

    def __init__(self, power: float = 1.0, **_) -> None:
        self._power = power

    def prepare(self, X, y, categorical_columns):
        n_neg, n_pos = self._counts(y)
        pos_weight = (n_neg / n_pos) ** self._power
        return BalancedTrainingSet(X, y, pos_weight=pos_weight,
                                   description=f"BCE pos_weight={pos_weight:.2f} ((n_neg/n_pos)^{self._power})")


@IMBALANCE_STRATEGIES.register("weighted_sampler")
class WeightedSampling(ImbalanceStrategy):
    """Re-balance the *mini-batches*: draw rows with probability inversely proportional to
    their class frequency (sampling with replacement), so each epoch sees ~50/50 batches."""

    def __init__(self, **_) -> None:
        pass

    def prepare(self, X, y, categorical_columns):
        n_neg, n_pos = self._counts(y)
        weights = np.where(y.to_numpy() == 1, 1.0 / n_pos, 1.0 / n_neg)
        return BalancedTrainingSet(X, y, sample_weights=weights, description="class-balanced WeightedRandomSampler")


@IMBALANCE_STRATEGIES.register("smotenc")
class SmoteNCOversampling(ImbalanceStrategy):
    """Synthesise minority rows by interpolating between minority neighbours.

    SMOTE-NC (not plain SMOTE) because the data is mixed-type: numeric columns are
    interpolated, categorical columns take the most frequent value among the neighbours —
    plain SMOTE would produce 'half Prepaid, half Business' rows.
    """

    def __init__(self, sampling_strategy: float = 0.5, k_neighbors: int = 5, seed: int = 42, **_) -> None:
        self._sampling_strategy, self._k, self._seed = sampling_strategy, k_neighbors, seed

    def prepare(self, X, y, categorical_columns):
        cats = [c for c in categorical_columns if c in X.columns]
        sampler = (SMOTENC(categorical_features=cats, sampling_strategy=self._sampling_strategy,
                           k_neighbors=self._k, random_state=self._seed) if cats else
                   SMOTE(sampling_strategy=self._sampling_strategy, k_neighbors=self._k, random_state=self._seed))
        X_res, y_res = sampler.fit_resample(X, y)
        X_res = pd.DataFrame(X_res, columns=X.columns).astype(X.dtypes.to_dict())
        return BalancedTrainingSet(X_res, pd.Series(y_res, name=y.name),
                                   description=f"SMOTE-NC to minority:majority={self._sampling_strategy}")


@IMBALANCE_STRATEGIES.register("random_undersample")
class RandomUndersampling(ImbalanceStrategy):
    """Drop majority rows at random until minority:majority == sampling_strategy.
    Cheap and honest, but discards information — viable only when data is plentiful."""

    def __init__(self, sampling_strategy: float = 0.5, seed: int = 42, **_) -> None:
        self._sampling_strategy, self._seed = sampling_strategy, seed

    def prepare(self, X, y, categorical_columns):
        X_res, y_res = RandomUnderSampler(sampling_strategy=self._sampling_strategy,
                                          random_state=self._seed).fit_resample(X, y)
        return BalancedTrainingSet(X_res, pd.Series(y_res, name=y.name),
                                   description=f"random under-sampling to minority:majority={self._sampling_strategy}")
