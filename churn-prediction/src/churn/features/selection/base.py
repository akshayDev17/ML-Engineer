"""Feature-selection abstractions.

A `FeatureSelector` receives the *training split only* and a list of candidate raw columns,
and returns which to keep plus a human-readable reason for every column it dropped. The
reasons end up in the run report and the model metadata, so "why is X not in the model?"
always has an answer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from churn.common.registry import Registry
from churn.data.schema import DatasetSchema

SELECTORS: Registry["FeatureSelector"] = Registry("feature selector")


@dataclass
class SelectionResult:
    selected: list[str]
    dropped: dict[str, str] = field(default_factory=dict)  # feature -> reason
    scores: dict[str, float] = field(default_factory=dict)  # feature -> score of the deciding stage


class FeatureSelector(ABC):
    @abstractmethod
    def select(self, X: pd.DataFrame, y: pd.Series, candidates: list[str]) -> SelectionResult: ...


class ChainedSelector(FeatureSelector):
    """Composite: run selectors in sequence, each seeing only the survivors of the previous."""

    def __init__(self, selectors: list[FeatureSelector]) -> None:
        self._selectors = selectors

    def select(self, X, y, candidates):
        survivors, dropped, scores = list(candidates), {}, {}
        for selector in self._selectors:
            result = selector.select(X, y, survivors)
            survivors = result.selected
            dropped.update(result.dropped)
            scores = result.scores or scores
        return SelectionResult(survivors, dropped, scores)


def encode_for_scoring(X: pd.DataFrame, schema: DatasetSchema, columns: list[str],
                       impute: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Quick numeric view for *scoring* features (not for training):
    numeric -> median-imputed; ordinal -> rank (NaN -> median rank); nominal -> integer code
    (NaN gets its own code). With impute=False numeric/ordinal NaNs are kept, e.g. for
    pairwise-complete correlations. Returns (matrix, is_discrete mask)."""
    cols, discrete = [], []
    for name in columns:
        s = X[name]
        spec = schema[name]
        if spec.ftype.is_numeric or name in schema.binary(columns):
            values = pd.to_numeric(s, errors="coerce")
            cols.append((values.fillna(values.median()) if impute else values).to_numpy(float))
            discrete.append(spec.ftype.value in ("discrete", "binary"))
        elif name in schema.ordinal(columns):
            ranks = s.map({c: i for i, c in enumerate(spec.categories)}).astype(float)
            cols.append((ranks.fillna(ranks.median()) if impute else ranks).to_numpy(float))
            discrete.append(True)
        else:
            codes, _ = pd.factorize(s.fillna("Missing"))
            cols.append(codes.astype(float))
            discrete.append(True)
    return np.column_stack(cols), np.array(discrete)
