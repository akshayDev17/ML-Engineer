"""Filter-family selectors: decide from data properties, before/without the final model."""
from __future__ import annotations

import pandas as pd
from sklearn.feature_selection import mutual_info_classif

from churn.data.schema import DatasetSchema
from churn.features.selection.base import FeatureSelector, SelectionResult, encode_for_scoring


def mutual_information(X: pd.DataFrame, y: pd.Series, schema: DatasetSchema, columns: list[str],
                       seed: int) -> dict[str, float]:
    matrix, discrete = encode_for_scoring(X, schema, columns)
    mi = mutual_info_classif(matrix, y.to_numpy(), discrete_features=discrete, random_state=seed)
    return {c: round(float(v), 5) for c, v in zip(columns, mi)}


class HygieneFilter(FeatureSelector):
    """Stage 1 — remove columns that must never reach a model, whatever their 'importance':

    1. leakage by contract  — not available at prediction time (schema flag)
    2. too sparse           — missing rate above a ceiling
    3. near-constant        — one value dominates; carries ~no information
    4. redundant            — |Spearman rho| above a ceiling with a kept feature; of the pair
                              we keep the one with higher mutual information with the target
    """

    def __init__(self, schema: DatasetSchema, seed: int, max_missing_rate: float = 0.5,
                 max_dominant_share: float = 0.98, redundancy_threshold: float = 0.85) -> None:
        self._schema = schema
        self._seed = seed
        self._max_missing = max_missing_rate
        self._max_dominant = max_dominant_share
        self._redundancy = redundancy_threshold

    def select(self, X, y, candidates):
        dropped: dict[str, str] = {}
        kept: list[str] = []
        for name in candidates:
            spec = self._schema[name]
            missing = X[name].isna().mean()
            dominant = X[name].value_counts(normalize=True, dropna=False).iloc[0]
            if not spec.available_at_prediction:
                dropped[name] = "leakage: value only exists after the outcome (schema contract)"
            elif missing > self._max_missing:
                dropped[name] = f"too sparse: {missing:.0%} missing"
            elif dominant > self._max_dominant:
                dropped[name] = f"near-constant: top value covers {dominant:.1%} of rows"
            else:
                kept.append(name)

        mi = mutual_information(X, y, self._schema, kept, self._seed)
        orderable = self._schema.numeric(kept) + self._schema.ordinal(kept)
        if len(orderable) > 1:
            # Pairwise-complete correlation: median-imputing first would dilute rho toward 0.
            matrix, _ = encode_for_scoring(X, self._schema, orderable, impute=False)
            rho = pd.DataFrame(matrix, columns=orderable).corr(method="spearman").abs()
            pairs = sorted(((rho.iat[i, j], orderable[i], orderable[j])
                            for i in range(len(orderable)) for j in range(i + 1, len(orderable))), reverse=True)
            for r, a, b in pairs:
                if r <= self._redundancy:
                    break
                if a in dropped or b in dropped:
                    continue
                loser, winner = (a, b) if mi[a] < mi[b] else (b, a)
                dropped[loser] = f"redundant: |rho|={r:.2f} with '{winner}' (which has higher MI)"
        survivors = [c for c in kept if c not in dropped]
        return SelectionResult(survivors, dropped, {c: mi[c] for c in survivors})


class MutualInformationSelector(FeatureSelector):
    """Univariate filter on mutual information (captures non-linear, not interaction, signal)."""

    def __init__(self, schema: DatasetSchema, seed: int, top_k: int | None = None,
                 min_mi: float = 0.001) -> None:
        self._schema, self._seed, self._top_k, self._min_mi = schema, seed, top_k, min_mi

    def select(self, X, y, candidates):
        mi = mutual_information(X, y, self._schema, candidates, self._seed)
        ranked = sorted(candidates, key=mi.get, reverse=True)
        keep = [c for c in ranked if mi[c] >= self._min_mi]
        if self._top_k is not None:
            keep = keep[: self._top_k]
        dropped = {c: f"low mutual information ({mi[c]:.4f})" for c in candidates if c not in keep}
        return SelectionResult([c for c in candidates if c in keep], dropped, mi)
