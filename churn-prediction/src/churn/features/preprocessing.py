"""Two-stage, schema-driven preprocessing (Builder + Facade).

    stage 1  "sanitize":  impute (median / most-frequent / 'Missing'), add missing-indicators,
                          cap extreme numeric outliers.  -> DataFrame, categories still strings
    stage 2  "encode":    log-transform skewed numerics, scale, one-hot nominals,
                          rank-encode ordinals.          -> float32 matrix for the network

Why two stages? Resampling methods such as SMOTENC must run on *imputed but not yet
one-hot-encoded* data (interpolating one-hot columns yields impossible half-categories).
The split gives the imbalance strategy a clean seam to plug into, and both stages are still
fitted exclusively on the training split.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, OrdinalEncoder, RobustScaler, StandardScaler

from churn.common.registry import Registry
from churn.data.schema import DatasetSchema
from churn.features.transformers import IQRCapper, SkewCorrector

SCALERS: Registry = Registry("scaler")
SCALERS.register("standard")(StandardScaler)
SCALERS.register("robust")(RobustScaler)
SCALERS.register("minmax")(MinMaxScaler)

MISSING_PREFIX = "missing_"


class TabularPreprocessor:
    def __init__(self, schema: DatasetSchema, features: list[str], scaler: str = "standard",
                 iqr_k: float = 3.0, skew_threshold: float = 1.0) -> None:
        self._schema = schema
        self._features = list(features)
        self._numeric = schema.numeric(self._features)
        self._nominal = schema.nominal(self._features)
        self._ordinal = schema.ordinal(self._features)
        self._binary = schema.binary(self._features)
        self._scaler_name = scaler
        self._iqr_k = iqr_k
        self._skew_threshold = skew_threshold
        self._sanitizer: ColumnTransformer | None = None
        self._encoder: ColumnTransformer | None = None

    # ------------------------------------------------------------------ public API
    @property
    def features(self) -> list[str]:
        return list(self._features)

    @property
    def is_fitted(self) -> bool:
        return self._sanitizer is not None and self._encoder is not None

    def fit_sanitizer(self, X: pd.DataFrame) -> "TabularPreprocessor":
        self._sanitizer = self._build_sanitizer().fit(X[self._features])
        return self

    def sanitize(self, X: pd.DataFrame) -> pd.DataFrame:
        if self._sanitizer is None:
            raise RuntimeError("fit_sanitizer() must be called first")
        out = self._sanitizer.transform(X[self._features])
        indicator_cols = [c for c in out.columns if c.startswith(MISSING_PREFIX)]
        out[indicator_cols] = out[indicator_cols].astype(float)
        for col in self._numeric + self._binary:
            out[col] = out[col].astype(float)
        return out

    def categorical_columns(self, sanitized: pd.DataFrame) -> list[str]:
        """Columns that are discrete *after* sanitizing (what SMOTENC must not interpolate)."""
        indicators = [c for c in sanitized.columns if c.startswith(MISSING_PREFIX)]
        return self._nominal + self._ordinal + self._binary + indicators

    def fit_encoder(self, sanitized: pd.DataFrame) -> "TabularPreprocessor":
        self._encoder = self._build_encoder().fit(sanitized)
        return self

    def encode(self, sanitized: pd.DataFrame) -> np.ndarray:
        if self._encoder is None:
            raise RuntimeError("fit_encoder() must be called first")
        return np.asarray(self._encoder.transform(sanitized), dtype=np.float32)

    def fit(self, X: pd.DataFrame) -> "TabularPreprocessor":
        return self.fit_sanitizer(X).fit_encoder(self.sanitize(X))

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        return self.encode(self.sanitize(X))

    @property
    def output_feature_names(self) -> list[str]:
        if self._encoder is None:
            raise RuntimeError("Preprocessor is not fitted")
        return list(self._encoder.get_feature_names_out())

    # ------------------------------------------------------------------ builders
    def _build_sanitizer(self) -> ColumnTransformer:
        transformers = [
            ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("cap", IQRCapper(self._iqr_k))]),
             self._numeric),
            ("nom", SimpleImputer(strategy="constant", fill_value="Missing"), self._nominal),
            ("ord", SimpleImputer(strategy="most_frequent"), self._ordinal),
            ("bin", SimpleImputer(strategy="most_frequent"), self._binary),
            # Missingness is often informative (who skips the CSAT survey?) — keep it as a feature.
            # Nominals don't need it: their 'Missing' category already becomes its own one-hot column.
            ("miss", MissingIndicator(features="missing-only"), self._numeric + self._ordinal + self._binary),
        ]
        ct = ColumnTransformer([t for t in transformers if t[2]], verbose_feature_names_out=False)
        ct.set_output(transform="pandas")
        # MissingIndicator names its outputs 'missingindicator_<col>' — normalise the prefix.
        return _RenamingColumnTransformer(ct)

    def _build_encoder(self) -> ColumnTransformer:
        ordinal_categories = [list(self._schema[c].categories) for c in self._ordinal]
        transformers = [
            ("num", Pipeline([("log", SkewCorrector(self._skew_threshold)),
                              ("scale", SCALERS.create(self._scaler_name))]), self._numeric),
            ("nom", OneHotEncoder(handle_unknown="ignore", sparse_output=False), self._nominal),
            ("ord", Pipeline([("rank", OrdinalEncoder(categories=ordinal_categories)),
                              ("scale", MinMaxScaler())]), self._ordinal),
        ]
        # binary flags and missing-indicators are already 0/1 -> passthrough.
        return ColumnTransformer([t for t in transformers if t[2]], remainder="passthrough",
                                 verbose_feature_names_out=False)


class _RenamingColumnTransformer:
    """Thin adapter: delegate to a ColumnTransformer, rename MissingIndicator outputs."""

    def __init__(self, inner: ColumnTransformer) -> None:
        self._inner = inner

    def fit(self, X, y=None):
        self._inner.fit(X, y)
        return self

    def transform(self, X) -> pd.DataFrame:
        out = self._inner.transform(X)
        return out.rename(columns=lambda c: c.replace("missingindicator_", MISSING_PREFIX))
