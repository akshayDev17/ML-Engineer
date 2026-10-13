"""Custom scikit-learn transformers (fit on train only; serialised inside the model bundle)."""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, OneToOneFeatureMixin, TransformerMixin
from sklearn.utils.validation import check_is_fitted, validate_data


class IQRCapper(OneToOneFeatureMixin, TransformerMixin, BaseEstimator):
    """Winsorise each column to [Q1 - k*IQR, Q3 + k*IQR] learned on the training data.

    k=1.5 is Tukey's inner fence ("outlier"), k=3.0 the outer fence ("extreme outlier").
    Capping keeps the row (a whale spender is real and informative) while stopping one
    value from dominating a gradient or a scaler's mean/std.
    """

    def __init__(self, k: float = 3.0) -> None:
        self.k = k

    def fit(self, X, y=None):
        X = validate_data(self, X, dtype=np.float64, ensure_all_finite="allow-nan")
        q1, q3 = np.nanpercentile(X, 25, axis=0), np.nanpercentile(X, 75, axis=0)
        iqr = q3 - q1
        self.lower_ = q1 - self.k * iqr
        self.upper_ = q3 + self.k * iqr
        return self

    def transform(self, X):
        check_is_fitted(self, ["lower_", "upper_"])
        X = validate_data(self, X, dtype=np.float64, reset=False, ensure_all_finite="allow-nan")
        return np.clip(X, self.lower_, self.upper_)


class SkewCorrector(OneToOneFeatureMixin, TransformerMixin, BaseEstimator):
    """Apply log1p to the columns that are strongly right-skewed *in the training data*.

    Which columns get transformed is itself learned (a fitted attribute), so the decision is
    frozen at fit time and replayed identically at serving time.
    """

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def fit(self, X, y=None):
        X = validate_data(self, X, dtype=np.float64)
        mean, std = X.mean(axis=0), X.std(axis=0)
        skew = np.where(std > 0, ((X - mean) ** 3).mean(axis=0) / np.where(std > 0, std, 1) ** 3, 0.0)
        self.skewness_ = skew
        self.log_mask_ = (skew > self.threshold) & (X.min(axis=0) >= 0)
        return self

    def transform(self, X):
        check_is_fitted(self, ["log_mask_"])
        X = validate_data(self, X, dtype=np.float64, reset=False).copy()
        X[:, self.log_mask_] = np.log1p(np.clip(X[:, self.log_mask_], 0, None))
        return X
