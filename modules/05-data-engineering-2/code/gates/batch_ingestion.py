"""Validates raw transaction batches against the schema, quarantines invalid rows with error reasons, and emits data-quality metrics."""

from dataclasses import dataclass

import pandas as pd
from pandera.errors import SchemaErrors

from schemas.transactions import Transaction


@dataclass
class GateResult:
    """Outcome of validating one batch/window."""

    valid: pd.DataFrame                # rows that passed every check
    invalid: pd.DataFrame              # rows that violated at least one check
    failure_cases: pd.DataFrame | None  # per-violation report (None if clean)
    is_clean: bool                     # True iff every row passed

    def metrics(self) -> dict:
        """Counts + failed columns — the M15 pillar-2 feed."""
        return {
            "rows_in": len(self.valid) + len(self.invalid),
            "rows_valid": len(self.valid),
            "rows_invalid": len(self.invalid),
            "failed_columns": (
                sorted(self.failure_cases["column"].dropna().unique().tolist())
                if self.failure_cases is not None
                else []
            ),
        }


def validate_batch(df: pd.DataFrame) -> GateResult:
    """Validate one batch. Never raises on bad data — returns the split.

    lazy=True collects ALL violations (not just the first), so the
    quarantine carries a complete error report and the feed can be fixed,
    not just survived. Column-level failures (strict, dtype) have no row
    index, so they flag the *whole batch* unclean rather than a single row.
    """
    try:
        Transaction.validate(df, lazy=True)
        return GateResult(valid=df, invalid=df.head(0), failure_cases=None, is_clean=True)
    except SchemaErrors as err:
        cases = err.failure_cases
        bad_idx = cases["index"].dropna().astype(int).unique()
        return GateResult(
            valid=df.drop(index=bad_idx),
            invalid=df.loc[bad_idx],
            failure_cases=cases,
            is_clean=False,
        )
