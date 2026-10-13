"""Train / validation / test splitting.

Each row is one customer at one snapshot (cross-sectional), the entity key is already
de-duplicated, and there is no time axis *across* rows — so a stratified random split is
the honest choice (M10). Stratification keeps the rare churn class at the same rate in
every split; with a ~10% minority an unstratified split could starve the test set.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split


@dataclass(frozen=True)
class Split:
    X: pd.DataFrame
    y: pd.Series

    def __len__(self) -> int:
        return len(self.y)

    @property
    def positive_rate(self) -> float:
        return float(self.y.mean())


@dataclass(frozen=True)
class DataSplits:
    train: Split
    val: Split
    test: Split

    def summary(self) -> dict[str, dict[str, float]]:
        return {name: {"rows": len(s), "positive_rate": round(s.positive_rate, 4)}
                for name, s in (("train", self.train), ("val", self.val), ("test", self.test))}


class DataSplitter(ABC):
    @abstractmethod
    def split(self, X: pd.DataFrame, y: pd.Series) -> DataSplits: ...


class StratifiedSplitter(DataSplitter):
    def __init__(self, val_size: float, test_size: float, seed: int) -> None:
        if val_size + test_size >= 0.6:
            raise ValueError("val_size + test_size leaves too little training data")
        self._val, self._test, self._seed = val_size, test_size, seed

    def split(self, X, y):
        X_rest, X_test, y_rest, y_test = train_test_split(
            X, y, test_size=self._test, stratify=y, random_state=self._seed)
        val_share_of_rest = self._val / (1.0 - self._test)
        X_train, X_val, y_train, y_val = train_test_split(
            X_rest, y_rest, test_size=val_share_of_rest, stratify=y_rest, random_state=self._seed)
        return DataSplits(Split(X_train, y_train), Split(X_val, y_val), Split(X_test, y_test))
