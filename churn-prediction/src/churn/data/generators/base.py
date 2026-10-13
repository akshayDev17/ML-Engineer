"""Template-Method base for synthetic churn data generators.

`generate()` fixes the *skeleton* every generator follows:

    sample features  ->  churn probability per row  ->  Bernoulli labels  ->  finalize

Subclasses only override the two hooks that genuinely differ (`_sample_features`,
`_churn_probability`). Everything that must be identical across generators — id format,
date materialisation, the leaky exit-survey column, column order — lives once, here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from churn.common.registry import Registry
from churn.data.schema import RAW_SCHEMA, DatasetSchema

# Internal column carried from sampling to finalisation; turned into `last_active_date`.
DAYS_INACTIVE = "_days_inactive"

# Marginal distributions shared by all generators (the "what does the population look like").
CATEGORICAL_MARGINALS: dict[str, dict[str, float]] = {
    "contract_type": {"Prepaid": 0.38, "Postpaid": 0.32, "Business": 0.14, "Family-Share": 0.16},
    "payment_method": {"Credit Card": 0.30, "Debit Card": 0.20, "Bank Transfer": 0.20, "E-Wallet": 0.18,
                       "Mailed Check": 0.12},
    "satisfaction_score": {"Very Dissatisfied": 0.08, "Dissatisfied": 0.15, "Neutral": 0.30, "Satisfied": 0.32,
                           "Very Satisfied": 0.15},
    "customer_tier": {"Bronze": 0.45, "Silver": 0.30, "Gold": 0.17, "Platinum": 0.08},
    "income_bracket": {"Low": 0.25, "Lower-Middle": 0.35, "Upper-Middle": 0.28, "High": 0.12},
    "region": {"North": 0.2, "South": 0.2, "East": 0.2, "West": 0.2, "Central": 0.2},
    "acquisition_channel": {"Online": 0.45, "Retail Store": 0.25, "Referral": 0.15, "Telesales": 0.15},
}

GENERATORS: Registry["ChurnDataGenerator"] = Registry("data generator")


class ChurnDataGenerator(ABC):
    def __init__(self, snapshot_date: str, seed: int, schema: DatasetSchema = RAW_SCHEMA) -> None:
        self._snapshot = pd.Timestamp(snapshot_date)
        self._seed = seed
        self._schema = schema

    # ------------------------------------------------------------------ template method
    def generate(self, n_rows: int, positive_rate: float) -> pd.DataFrame:
        if not 0.0 < positive_rate < 1.0:
            raise ValueError("positive_rate must be in (0, 1)")
        rng = np.random.default_rng(self._seed)
        features = self._sample_features(rng, n_rows)
        proba = self._churn_probability(features, positive_rate, rng)
        churn = rng.binomial(1, proba)
        return self._finalize(features, churn, rng)

    # ------------------------------------------------------------------ hooks
    @abstractmethod
    def _sample_features(self, rng: np.random.Generator, n: int) -> pd.DataFrame:
        """Return every raw feature column plus `DAYS_INACTIVE` (no id, no label)."""

    @abstractmethod
    def _churn_probability(self, features: pd.DataFrame, positive_rate: float,
                           rng: np.random.Generator) -> np.ndarray:
        """P(churn | features) for each row; its mean should be ~positive_rate."""

    # ------------------------------------------------------------------ shared helpers
    @staticmethod
    def _sample_categorical(rng: np.random.Generator, column: str, n: int) -> np.ndarray:
        marginal = CATEGORICAL_MARGINALS[column]
        return rng.choice(list(marginal), size=n, p=list(marginal.values()))

    def _finalize(self, features: pd.DataFrame, churn: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
        df = features.copy()
        n = len(df)
        df[self._schema.id_column] = [f"CUST-{i:06d}" for i in rng.permutation(n) + 1]
        days = df.pop(DAYS_INACTIVE).to_numpy()
        df["last_active_date"] = (self._snapshot - pd.to_timedelta(days, unit="D")).strftime("%Y-%m-%d")
        df[self._schema.target] = churn
        # Leakage by construction: the exit survey only exists for customers who already left.
        survey = rng.integers(1, 6, size=n).astype(float)
        responded = (churn == 1) & (rng.random(n) < 0.85)
        df["exit_survey_score"] = np.where(responded, survey, np.nan)
        return df[self._schema.columns]
