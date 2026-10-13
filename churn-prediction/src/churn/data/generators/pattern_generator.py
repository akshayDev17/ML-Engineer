"""ADVANCED generator: data synthesised from an explicitly *assumed* causal pattern.

The story (documented in notes/01_data_generation.md):

* Two unobserved latents drive behaviour: `engagement` and `satisfaction`.
  - engagement  -> longer sessions, fewer days since last activity
  - satisfaction-> CSAT answer, fewer support tickets
* Tenure drives loyalty tier; contract type and product count drive the bill;
  tenure x bill drives lifetime charges (a redundant feature on purpose).
* Churn log-odds are an additive model of those observables, with
  - non-linear terms (early-tenure hazard, log-recency, U-shaped age)
  - interactions (tickets hurt more when dissatisfied; price hurts prepaid more)
  - pure-noise columns with zero effect (region, marketing emails)
* The intercept is solved numerically so that the mean churn probability equals the
  requested positive rate — that is how `--imbalance-ratio` is honoured *without*
  destroying the pattern.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from churn.data.generators.base import CATEGORICAL_MARGINALS, DAYS_INACTIVE, GENERATORS, ChurnDataGenerator

CONTRACT_EFFECT = {"Prepaid": 1.0, "Postpaid": 0.0, "Business": -0.8, "Family-Share": -0.5}
PAYMENT_EFFECT = {"Credit Card": -0.2, "Debit Card": 0.0, "Bank Transfer": -0.4, "E-Wallet": 0.5, "Mailed Check": 0.7}
CHANNEL_EFFECT = {"Online": 0.0, "Retail Store": -0.1, "Referral": -0.4, "Telesales": 0.35}
CONTRACT_BILL = {"Prepaid": 0.0, "Postpaid": 10.0, "Business": 35.0, "Family-Share": 20.0}


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _ordinal_from_latent(latent: np.ndarray, column: str) -> np.ndarray:
    """Cut a continuous latent into ordered levels so that the level shares match the marginal."""
    levels = list(CATEGORICAL_MARGINALS[column])
    cum = np.cumsum(list(CATEGORICAL_MARGINALS[column].values()))[:-1]
    idx = np.digitize(latent, np.quantile(latent, cum))
    return np.asarray(levels, dtype=object)[idx]


@GENERATORS.register("pattern")
class PatternChurnDataGenerator(ChurnDataGenerator):
    def _sample_features(self, rng: np.random.Generator, n: int) -> pd.DataFrame:
        engagement = rng.normal(0, 1, n)
        satisfaction = rng.normal(0, 1, n)

        tenure = np.clip(rng.gamma(1.5, 18.0, n), 1, 120).round()
        tier = _ordinal_from_latent(tenure / 30 + rng.normal(0, 0.7, n), "customer_tier")
        tier_rank = pd.Series(tier).map({t: i for i, t in enumerate(CATEGORICAL_MARGINALS["customer_tier"])}).to_numpy()

        contract = self._sample_categorical(rng, "contract_type", n)
        is_business = contract == "Business"
        is_family = contract == "Family-Share"
        products = np.clip(1 + rng.poisson(0.6 + 0.6 * is_business + 0.4 * is_family + 0.3 * tier_rank), 1, 8)

        bill_premium = pd.Series(contract).map(CONTRACT_BILL).to_numpy()
        monthly = np.clip(15 + 14 * products + bill_premium + rng.normal(0, 8, n), 10, None).round(2)
        discount = np.where(rng.random(n) < 0.3, 0.0, np.clip(rng.beta(2, 8, n) * 40 + 2 * tier_rank, 0, 60)).round(1)
        total = (tenure * monthly * (1 - discount / 100) * rng.normal(1.0, 0.05, n)).round(2)

        return pd.DataFrame({
            "transaction_amount": rng.lognormal(np.log(monthly * 1.1), 0.45).round(2),
            "contract_type": contract,
            "payment_method": self._sample_categorical(rng, "payment_method", n),
            "tenure_months": tenure.astype(int),
            "monthly_charges": monthly,
            "total_charges": total,
            "num_support_tickets": rng.poisson(np.exp(-0.2 - 0.6 * satisfaction)),
            "num_products": products,
            "age": np.clip(rng.normal(42, 13, n), 18, 85).round().astype(int),
            "avg_session_minutes": rng.gamma(2.0, 12.0 * np.exp(0.4 * engagement)).round(1),
            "discount_pct": discount,
            "satisfaction_score": _ordinal_from_latent(satisfaction + rng.normal(0, 0.5, n), "satisfaction_score"),
            "customer_tier": tier,
            "income_bracket": self._sample_categorical(rng, "income_bracket", n),
            "region": self._sample_categorical(rng, "region", n),
            "acquisition_channel": self._sample_categorical(rng, "acquisition_channel", n),
            "is_paperless_billing": np.where(rng.random(n) < 0.6, "Yes", "No"),
            "marketing_emails_opened": rng.poisson(3.0, n),
            DAYS_INACTIVE: np.clip(rng.exponential(6.0 * np.exp(-0.9 * engagement)), 0, 365).round().astype(int),
        })

    def _churn_probability(self, f: pd.DataFrame, positive_rate: float, rng: np.random.Generator) -> np.ndarray:
        sat_rank = f["satisfaction_score"].map(
            {s: i for i, s in enumerate(CATEGORICAL_MARGINALS["satisfaction_score"])}).to_numpy()
        tier_rank = f["customer_tier"].map(
            {t: i for i, t in enumerate(CATEGORICAL_MARGINALS["customer_tier"])}).to_numpy()
        is_prepaid = (f["contract_type"] == "Prepaid").to_numpy()
        dissatisfied = sat_rank <= 1
        tenure = f["tenure_months"].to_numpy()
        tickets = f["num_support_tickets"].to_numpy()

        score = (
            f["contract_type"].map(CONTRACT_EFFECT).to_numpy()
            + f["payment_method"].map(PAYMENT_EFFECT).to_numpy()
            + f["acquisition_channel"].map(CHANNEL_EFFECT).to_numpy()
            + 1.2 * np.exp(-tenure / 8.0) - 0.01 * tenure                       # early-tenure hazard
            + 0.8 * (np.log1p(f[DAYS_INACTIVE].to_numpy()) - np.log1p(7))       # recency, log-shaped
            + 0.30 * tickets * (1 + 0.6 * dissatisfied)                          # interaction
            - 0.45 * (sat_rank - 2)
            + 0.015 * (f["monthly_charges"].to_numpy() - 60) * (1 + is_prepaid)  # price x contract
            - 0.04 * f["discount_pct"].to_numpy()
            - 0.25 * (f["num_products"].to_numpy() - 1)
            - 0.20 * tier_rank
            - 0.15 * (np.log(f["transaction_amount"].to_numpy()) - np.log(80))
            + 0.0006 * (f["age"].to_numpy() - 42) ** 2                          # U-shaped age
            + 0.15 * (f["is_paperless_billing"] == "Yes").to_numpy()
            + rng.normal(0, 0.3, len(f))                                        # unobserved heterogeneity
        )
        return _sigmoid(self._calibrate_intercept(score, positive_rate) + score)

    @staticmethod
    def _calibrate_intercept(score: np.ndarray, target_rate: float) -> float:
        """Bisection for b0 such that mean(sigmoid(b0 + score)) == target_rate (monotone in b0)."""
        lo, hi = -30.0, 30.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if _sigmoid(mid + score).mean() > target_rate:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
