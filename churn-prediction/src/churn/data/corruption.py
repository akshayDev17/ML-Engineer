"""Make clean synthetic data realistically dirty.

Each kind of dirt is a small `Corruption` strategy (Single Responsibility); `DirtyDataInjector`
is a Composite that applies a battery of them in order and records what it did. The
battery mirrors what real CRM/billing extracts look like:

    null tokens, inconsistent category spellings, numbers stored as formatted text,
    impossible values, extreme-but-valid outliers, mixed date formats and future dates,
    duplicate records, and labels encoded five different ways (some missing).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from churn.data.schema import DatasetSchema, FeatureType


def _pick(rng: np.random.Generator, n: int, rate: float) -> np.ndarray:
    return np.flatnonzero(rng.random(n) < rate)


def _as_object(df: pd.DataFrame, column: str) -> None:
    # pandas>=3 refuses to silently upcast; dirty columns must be allowed to hold mixed types.
    df[column] = df[column].astype(object)


class Corruption(ABC):
    name: str = "corruption"

    @abstractmethod
    def apply(self, df: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, int]:
        """Return the corrupted frame and the number of cells/rows touched."""


class NullTokenInjection(Corruption):
    """Missing values, spelled the many ways real exports spell them."""

    name = "null_tokens"
    TOKENS = (None, "", "N/A", "null", "?", "-", "NaN", "none", "  ")

    def __init__(self, columns: list[str], rate: float) -> None:
        self._columns, self._rate = columns, rate

    def apply(self, df, rng):
        touched = 0
        for col in self._columns:
            idx = _pick(rng, len(df), self._rate)
            if len(idx):
                _as_object(df, col)
                tokens = rng.choice(np.array(self.TOKENS, dtype=object), size=len(idx))
                df.loc[df.index[idx], col] = tokens
                touched += len(idx)
        return df, touched


class CategoricalTextNoise(Corruption):
    """Case, whitespace and alias variants: 'Prepaid' -> ' PREPAID', 'pre-paid', 'prepaid  '."""

    name = "categorical_text_noise"

    def __init__(self, schema: DatasetSchema, columns: list[str], rate: float) -> None:
        self._schema, self._columns, self._rate = schema, columns, rate

    def apply(self, df, rng):
        touched = 0
        for col in self._columns:
            spec = self._schema[col]
            reverse_alias: dict[str, list[str]] = {}
            for alias, canonical in spec.aliases.items():
                reverse_alias.setdefault(canonical, []).append(alias)
            idx = _pick(rng, len(df), self._rate)
            _as_object(df, col)
            for i in df.index[idx]:
                value = df.at[i, col]
                if not isinstance(value, str) or not value.strip():
                    continue
                variants = [value.lower(), value.upper(), f"  {value} ", value.replace("-", " ")]
                variants += reverse_alias.get(value, [])
                df.at[i, col] = variants[rng.integers(len(variants))]
                touched += 1
        return df, touched


class NumericFormattingNoise(Corruption):
    """Numbers exported as formatted text: '$1,234.50', 'USD 81.1', '12 months'."""

    name = "numeric_formatting_noise"

    def __init__(self, column: str, rate: float, formatters: list[Callable[[float], str]]) -> None:
        self._column, self._rate, self._formatters = column, rate, formatters

    def apply(self, df, rng):
        idx = _pick(rng, len(df), self._rate)
        _as_object(df, self._column)
        touched = 0
        for i in df.index[idx]:
            value = df.at[i, self._column]
            if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
                fmt = self._formatters[rng.integers(len(self._formatters))]
                df.at[i, self._column] = fmt(float(value))
                touched += 1
        return df, touched


class InvalidValueInjection(Corruption):
    """Physically impossible values (age 999, negative tenure, 150% discount)."""

    name = "invalid_values"

    def __init__(self, column: str, rate: float, values: list) -> None:
        self._column, self._rate, self._values = column, rate, values

    def apply(self, df, rng):
        idx = _pick(rng, len(df), self._rate)
        if len(idx):
            _as_object(df, self._column)
            df.loc[df.index[idx], self._column] = rng.choice(np.array(self._values, dtype=object), size=len(idx))
        return df, len(idx)


class OutlierInjection(Corruption):
    """Extreme but *possible* values (a whale spender) — to be capped, not deleted."""

    name = "outliers"

    def __init__(self, column: str, rate: float, factor: tuple[float, float] = (8.0, 40.0)) -> None:
        self._column, self._rate, self._factor = column, rate, factor

    def apply(self, df, rng):
        idx = _pick(rng, len(df), self._rate)
        values = pd.to_numeric(df[self._column], errors="coerce")
        touched = 0
        _as_object(df, self._column)
        for i in df.index[idx]:
            if not pd.isna(values.at[i]):
                df.at[i, self._column] = round(float(values.at[i]) * rng.uniform(*self._factor), 2)
                touched += 1
        return df, touched


class DateNoise(Corruption):
    """Mixed date formats, unparseable strings, and dates in the future (clock/ETL bugs)."""

    name = "date_noise"
    FORMATS = ("%d-%b-%Y", "%Y/%m/%d", "%b %d, %Y", "%Y%m%d")
    GARBAGE = ("0000-00-00", "not available", "31-02-2026")

    def __init__(self, column: str, rate: float, snapshot_date: str) -> None:
        self._column, self._rate = column, rate
        self._snapshot = pd.Timestamp(snapshot_date)

    def apply(self, df, rng):
        idx = _pick(rng, len(df), self._rate)
        _as_object(df, self._column)
        touched = 0
        for i in df.index[idx]:
            parsed = pd.to_datetime(df.at[i, self._column], format="%Y-%m-%d", errors="coerce")
            if pd.isna(parsed):
                continue
            roll = rng.random()
            if roll < 0.75:
                df.at[i, self._column] = parsed.strftime(self.FORMATS[rng.integers(len(self.FORMATS))])
            elif roll < 0.9:
                df.at[i, self._column] = self.GARBAGE[rng.integers(len(self.GARBAGE))]
            else:
                future = self._snapshot + pd.Timedelta(days=int(rng.integers(5, 400)))
                df.at[i, self._column] = future.strftime("%Y-%m-%d")
            touched += 1
        return df, touched


class DuplicateRecords(Corruption):
    """Re-ingested rows; some with a differently-formatted id (' cust-000123 ')."""

    name = "duplicate_records"

    def __init__(self, id_column: str, rate: float) -> None:
        self._id_column, self._rate = id_column, rate

    def apply(self, df, rng):
        idx = _pick(rng, len(df), self._rate)
        dupes = df.iloc[idx].copy()
        messy = rng.random(len(dupes)) < 0.5
        dupes.loc[messy, self._id_column] = [f" {v.lower()} " for v in dupes.loc[messy, self._id_column]]
        return pd.concat([df, dupes], ignore_index=True), len(dupes)


class LabelNoise(Corruption):
    """The target, encoded inconsistently — and occasionally missing."""

    name = "label_noise"
    POSITIVE = ("Yes", "yes", "1", "TRUE", "churned", "Y")
    NEGATIVE = ("No", "no", "0", "FALSE", "stayed", "N")

    def __init__(self, target: str, rate: float, missing_rate: float) -> None:
        self._target, self._rate, self._missing_rate = target, rate, missing_rate

    def apply(self, df, rng):
        _as_object(df, self._target)
        idx = _pick(rng, len(df), self._rate)
        for i in df.index[idx]:
            pool = self.POSITIVE if int(df.at[i, self._target]) == 1 else self.NEGATIVE
            df.at[i, self._target] = pool[rng.integers(len(pool))]
        missing = _pick(rng, len(df), self._missing_rate)
        df.loc[df.index[missing], self._target] = None
        return df, len(idx) + len(missing)


@dataclass
class CorruptionReport:
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, name: str, n: int) -> None:
        self.counts[name] = self.counts.get(name, 0) + n


class DirtyDataInjector:
    """Composite of `Corruption`s; order matters (e.g. duplicates are made from dirty rows)."""

    def __init__(self, corruptions: list[Corruption], seed: int) -> None:
        self._corruptions = corruptions
        self._seed = seed

    def inject(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CorruptionReport]:
        rng = np.random.default_rng(self._seed)
        report = CorruptionReport()
        out = df.copy()
        for corruption in self._corruptions:
            out, n = corruption.apply(out, rng)
            report.add(corruption.name, n)
        out = out.sample(frac=1.0, random_state=self._seed).reset_index(drop=True)
        return out, report

    @classmethod
    def default(cls, schema: DatasetSchema, rate: float, snapshot_date: str, seed: int) -> "DirtyDataInjector":
        categorical = schema.of_type(FeatureType.NOMINAL, FeatureType.ORDINAL, FeatureType.BINARY)
        numeric = [c for c in schema.of_type(FeatureType.CONTINUOUS, FeatureType.DISCRETE)
                   if schema[c].available_at_prediction]
        money = [lambda v: f"${v:,.2f}", lambda v: f"USD {v:.2f}", lambda v: f"{v:,.2f} "]
        corruptions: list[Corruption] = [
            # Outliers/invalids first, while columns are still numeric.
            OutlierInjection("transaction_amount", rate / 2),
            OutlierInjection("avg_session_minutes", rate / 4),
            InvalidValueInjection("age", rate / 2, [999, -1, 0, 150]),
            InvalidValueInjection("tenure_months", rate / 4, [-3, -12]),
            InvalidValueInjection("discount_pct", rate / 4, [150.0, -20.0]),
            InvalidValueInjection("transaction_amount", rate / 4, [-50.0, -9.99]),
            NumericFormattingNoise("transaction_amount", rate * 2, money),
            NumericFormattingNoise("total_charges", rate, money),
            NumericFormattingNoise("tenure_months", rate, [lambda v: f"{int(v)} months", lambda v: f"{int(v)}m"]),
            CategoricalTextNoise(schema, categorical, rate * 2),
            DateNoise("last_active_date", rate * 2, snapshot_date),
            NullTokenInjection(numeric + categorical + ["last_active_date"], rate),
            DuplicateRecords(schema.id_column, rate / 2),
            LabelNoise(schema.target, rate * 2, missing_rate=rate / 4),
        ]
        return cls(corruptions, seed)
