"""Stateless, deterministic feature derivation (safe before the split, reused at serving)."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DerivedFeature(ABC):
    @abstractmethod
    def add(self, df: pd.DataFrame) -> pd.DataFrame: ...


class RecencyFeature(DerivedFeature):
    """Dates are not model inputs; *time since* a date, relative to the as-of date, is.

    The as-of date is the training snapshot when building the dataset and "now" at serving
    time — the same definition evaluated at prediction time (point-in-time correctness, M4).
    """

    def __init__(self, date_column: str, output: str, as_of: str | pd.Timestamp) -> None:
        self._date, self._out, self._as_of = date_column, output, pd.Timestamp(as_of)

    def add(self, df):
        df[self._out] = (self._as_of - pd.to_datetime(df[self._date])).dt.days.astype(float)
        return df.drop(columns=[self._date])


class FeatureEngineer:
    def __init__(self, features: list[DerivedFeature]) -> None:
        self._features = features

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for feature in self._features:
            out = feature.add(out)
        return out

    @classmethod
    def default(cls, as_of: str | pd.Timestamp) -> "FeatureEngineer":
        return cls([RecencyFeature("last_active_date", "days_since_last_active", as_of)])
