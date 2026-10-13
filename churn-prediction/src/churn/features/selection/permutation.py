"""Model-agnostic, cross-validated permutation importance (the main selection stage).

For each stratified fold of the *training split*:
    fit a fast non-linear proxy (HistGradientBoosting) on the other folds,
    then, on the held-out fold, shuffle one raw column at a time and measure the drop in
    average precision (PR-AUC).
A feature is kept when its importance is consistently positive across folds and repeats
(mean - stability_k * std > min_importance). Permuting the *raw* column permutes all of its one-hot
children together, so a nominal feature is judged as one feature.

Validation and test splits are never touched here: they stay clean for early stopping,
threshold selection and the final unbiased estimate.
"""
from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OrdinalEncoder

from churn.data.schema import DatasetSchema
from churn.features.selection.base import FeatureSelector, SelectionResult


class PermutationImportanceSelector(FeatureSelector):
    def __init__(self, schema: DatasetSchema, seed: int, n_splits: int = 5, n_repeats: int = 5,
                 scoring: str = "average_precision", min_importance: float = 0.0, stability_k: float = 1.0,
                 min_features: int = 3) -> None:
        self._schema = schema
        self._seed = seed
        self._n_splits = n_splits
        self._n_repeats = n_repeats
        self._scoring = scoring
        self._min_importance = min_importance
        self._stability_k = stability_k
        self._min_features = min_features

    def _proxy_model(self, candidates: list[str]) -> Pipeline:
        numeric = self._schema.numeric(candidates) + self._schema.binary(candidates)
        categorical = self._schema.nominal(candidates) + self._schema.ordinal(candidates)
        prep = ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), numeric),
            ("cat", make_pipeline(
                SimpleImputer(strategy="constant", fill_value="Missing"),
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)), categorical),
        ])
        is_categorical = [False] * len(numeric) + [True] * len(categorical)
        model = HistGradientBoostingClassifier(
            categorical_features=is_categorical, class_weight="balanced", max_iter=200,
            learning_rate=0.08, random_state=self._seed)
        return Pipeline([("prep", prep), ("model", model)])

    def select(self, X, y, candidates):
        X = X[candidates]
        folds = StratifiedKFold(self._n_splits, shuffle=True, random_state=self._seed)
        per_run = []
        for fold, (fit_idx, held_idx) in enumerate(folds.split(X, y)):
            model = self._proxy_model(candidates).fit(X.iloc[fit_idx], y.iloc[fit_idx])
            result = permutation_importance(
                model, X.iloc[held_idx], y.iloc[held_idx], scoring=self._scoring,
                n_repeats=self._n_repeats, random_state=self._seed + fold)
            per_run.append(result.importances)  # (n_features, n_repeats)
        importances = np.concatenate(per_run, axis=1)
        mean, std = importances.mean(axis=1), importances.std(axis=1)

        keep = [c for c, m, s in zip(candidates, mean, std) if m - self._stability_k * s > self._min_importance]
        if len(keep) < self._min_features:  # guarantee a usable model even on signal-free data
            order = np.argsort(-mean)[: self._min_features]
            keep = [candidates[i] for i in sorted(order)]
        dropped = {c: f"permutation importance not reliably > 0 (mean={m:+.4f}, std={s:.4f})"
                   for c, m, s in zip(candidates, mean, std) if c not in keep}
        scores = {c: round(float(m), 5) for c, m in zip(candidates, mean)}
        return SelectionResult([c for c in candidates if c in keep], dropped, scores)
