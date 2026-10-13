"""VANILLA generator: realistic marginals, but *no* relationship between features and churn.

Every column is drawn independently and the label is a coin flip at the requested rate.
A correct pipeline must therefore score ~0.5 ROC-AUC on this data. That makes it a useful
negative control: if the pipeline reports real skill here, something is leaking.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from churn.data.generators.base import DAYS_INACTIVE, GENERATORS, ChurnDataGenerator


@GENERATORS.register("random")
class RandomChurnDataGenerator(ChurnDataGenerator):
    def _sample_features(self, rng: np.random.Generator, n: int) -> pd.DataFrame:
        tenure = np.clip(rng.gamma(1.5, 18.0, n), 1, 120).round()
        monthly = np.clip(rng.normal(65, 25, n), 10, None).round(2)
        discount = np.where(rng.random(n) < 0.3, 0.0, (rng.beta(2, 8, n) * 40).round(1))
        return pd.DataFrame({
            "transaction_amount": rng.lognormal(np.log(70), 0.5, n).round(2),
            "contract_type": self._sample_categorical(rng, "contract_type", n),
            "payment_method": self._sample_categorical(rng, "payment_method", n),
            "tenure_months": tenure.astype(int),
            "monthly_charges": monthly,
            "total_charges": (tenure * monthly * rng.normal(1.0, 0.05, n)).round(2),
            "num_support_tickets": rng.poisson(1.0, n),
            "num_products": np.clip(1 + rng.poisson(0.9, n), 1, 8),
            "age": np.clip(rng.normal(42, 13, n), 18, 85).round().astype(int),
            "avg_session_minutes": rng.gamma(2.0, 12.0, n).round(1),
            "discount_pct": discount,
            "satisfaction_score": self._sample_categorical(rng, "satisfaction_score", n),
            "customer_tier": self._sample_categorical(rng, "customer_tier", n),
            "income_bracket": self._sample_categorical(rng, "income_bracket", n),
            "region": self._sample_categorical(rng, "region", n),
            "acquisition_channel": self._sample_categorical(rng, "acquisition_channel", n),
            "is_paperless_billing": np.where(rng.random(n) < 0.6, "Yes", "No"),
            "marketing_emails_opened": rng.poisson(3.0, n),
            DAYS_INACTIVE: np.clip(rng.exponential(10.0, n), 0, 365).round().astype(int),
        })

    def _churn_probability(self, features, positive_rate, rng) -> np.ndarray:
        return np.full(len(features), positive_rate)
