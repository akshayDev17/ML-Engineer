"""Simulate a raw transaction feed to disk for the batch and stream runners.

A real pipeline reads from an upstream feed; here we write that feed to
disk — one clean file, and one that "goes bad" (the M5 silent-change
scenario, materialized as data).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

MERCHANT_CODES = ["5812", "5411", "5814", "4121", "6011"]


def pure_transactions(n: int, seed: int = 0) -> pd.DataFrame:
    """A frame where every row satisfies the Transaction schema."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i:05d}" for i in range(n)],
            "amount": np.round(rng.uniform(0.5, 500.0, n), 2),
            "merchant_category": rng.choice(MERCHANT_CODES, n),
            "event_ts": pd.date_range("2024-01-01", periods=n, freq="min"),
        }
    )


def contaminate(df: pd.DataFrame, n_bad: int, seed: int = 0) -> pd.DataFrame:
    """Append rule-violating rows (fresh ids, one rule per row).

    Rules cycle through four:
      0  negative amount          -> Field(ge=0)
      1  bad merchant_category    -> str_matches (non-4-digit)
      2  null event_ts            -> nullable=False
      3  non-datetime event_ts    -> dtype('datetime64[ns]')  (type violation)
    """
    rng = np.random.default_rng(seed)
    bad = df.copy()
    for k in range(n_bad):
        src = int(rng.integers(0, len(bad)))
        row = bad.iloc[src : src + 1].copy()  # preserves dtypes
        row.loc[:, "transaction_id"] = f"TXN-BAD-{len(bad):05d}"
        rule = k % 4
        if rule == 0:
            row.loc[:, "amount"] = -abs(row["amount"].iloc[0]) - 1.0
        elif rule == 1:
            row.loc[:, "merchant_category"] = "abcd"
        elif rule == 2:
            row.loc[:, "event_ts"] = pd.NaT
        else:  # type violation: a non-datetime value in event_ts
            row["event_ts"] = row["event_ts"].astype(object)
            row.loc[:, "event_ts"] = "not-a-date"
        bad = pd.concat([bad, row], ignore_index=True)
    return bad


def main() -> None:
    p = argparse.ArgumentParser(description="Simulate a raw transaction feed to disk.")
    p.add_argument("--out", default="data", help="output directory")
    p.add_argument("--n", type=int, default=200, help="rows in the clean feed")
    p.add_argument("--bad", type=int, default=4, help="violating rows to inject")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pure = pure_transactions(args.n, args.seed)
    dirty = contaminate(pure, args.bad, args.seed)

    pure.to_csv(out / "transactions_clean.csv", index=False)
    dirty.to_csv(out / "transactions_contaminated.csv", index=False)
    print(f"wrote {len(pure)} clean rows            -> {out / 'transactions_clean.csv'}")
    print(f"wrote {len(dirty)} rows ({args.bad} bad) -> {out / 'transactions_contaminated.csv'}")


if __name__ == "__main__":
    main()
