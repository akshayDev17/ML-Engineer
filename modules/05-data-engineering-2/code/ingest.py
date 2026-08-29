"""Ingestion I/O: read the raw transaction feed under its dtype contract.

CSV round-trips lose types — "5812" becomes an int, datetimes become
strings. The read re-declares the contract so the schema sees what the
producer wrote. In production you'd land Parquet or read from a warehouse
with a declared schema; the discipline is identical.
"""

import pandas as pd

DTYPES = {
    "transaction_id": str,
    "amount": float,
    "merchant_category": str,  # keep "5812" a string, not an int
}

PARSE_DATES = ["event_ts"]


def read_transactions(path: str) -> pd.DataFrame:
    """Read a raw transaction feed (batch) with its dtype contract."""
    return pd.read_csv(path, dtype=DTYPES, parse_dates=PARSE_DATES)
