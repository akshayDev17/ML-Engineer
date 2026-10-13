"""Row-level, *stateless* cleaning.

Design rule that keeps this leakage-free: a cleaning step may only use the schema (the
contract) and the row itself — never statistics of the dataset. Anything that *learns* from
data (imputation medians, outlier fences, scaling) is a fitted transformer in
`churn.features.preprocessing` and is fitted on the training split only.

Because the steps are stateless they are safe to run before the split, and the very same
`DataCleaner` is reused by the serving predictor — one code path, no train/serve skew (M6).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from churn.data.schema import DatasetSchema, FeatureType

NULL_TOKENS = {"", "na", "n/a", "nan", "null", "none", "?", "-", "--", "missing"}
POSITIVE_LABELS = {"1", "yes", "y", "true", "churned", "churn"}
NEGATIVE_LABELS = {"0", "no", "n", "false", "stayed", "retained"}
DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%Y/%m/%d", "%b %d, %Y", "%Y%m%d")


def _to_text(value) -> str | None:
    """Normalise any scalar to lowercase text ('1.0' -> '1') so lookups are type-agnostic."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (int, float, np.integer, np.floating)) and float(value).is_integer():
        return str(int(value))
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _n_changed(before: pd.Series, after: pd.Series) -> int:
    """Cells whose value changed; two missing values count as equal."""
    b, a = before.map(_to_text), after.map(_to_text)
    both_missing = b.isna() & a.isna()
    return int(((b != a) & ~both_missing).sum())


class CleaningStep(ABC):
    name: str = "step"

    @abstractmethod
    def apply(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Return the cleaned frame and how many cells/rows this step changed."""


class NormalizeNullTokens(CleaningStep):
    name = "null_tokens_to_nan"

    def apply(self, df):
        changed = 0
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                as_text = df[col].map(_to_text)
                mask = as_text.isin(NULL_TOKENS) & df[col].notna()
                changed += int(mask.sum())
                df[col] = df[col].astype(object).where(~mask, np.nan)
        return df, changed


class NormalizeIdentifier(CleaningStep):
    name = "normalize_identifier"

    def __init__(self, id_column: str) -> None:
        self._col = id_column

    def apply(self, df):
        if self._col not in df:
            return df, 0
        before = df[self._col].astype(object)
        after = before.map(lambda v: v if pd.isna(v) else str(v).strip().upper()).astype(object)
        df[self._col] = after
        return df, int(((before != after) & before.notna()).sum())


class ParseTarget(CleaningStep):
    """Map every label spelling onto {0, 1}; rows without a usable label are dropped."""

    name = "parse_target_drop_unlabelled"

    def __init__(self, target: str) -> None:
        self._target = target

    def apply(self, df):
        text = df[self._target].map(_to_text)
        parsed = np.where(text.isin(POSITIVE_LABELS), 1.0, np.where(text.isin(NEGATIVE_LABELS), 0.0, np.nan))
        df[self._target] = parsed
        keep = ~np.isnan(parsed)
        dropped = int((~keep).sum())
        df = df.loc[keep].copy()
        df[self._target] = df[self._target].astype(int)
        return df, dropped


class ParseNumeric(CleaningStep):
    """'$1,234.50' -> 1234.5, '12 months' -> 12, garbage -> NaN."""

    name = "parse_numeric_text"

    def __init__(self, columns: list[str]) -> None:
        self._columns = columns

    def apply(self, df):
        changed = 0
        for col in self._columns:
            if col not in df:
                continue
            raw = df[col]
            if pd.api.types.is_numeric_dtype(raw):
                continue
            stripped = raw.map(lambda v: v if pd.isna(v) or not isinstance(v, str) else re.sub(r"[^0-9.\-]", "", v))
            changed += _n_changed(raw, stripped)
            df[col] = pd.to_numeric(stripped, errors="coerce").astype(float)
        return df, changed


class CanonicalizeCategories(CleaningStep):
    """Case/whitespace/alias variants -> the schema's canonical category; unknown -> NaN.

    Binary columns are additionally mapped to 0.0/1.0 (index in the schema's category tuple).
    """

    name = "canonicalize_categories"

    def __init__(self, schema: DatasetSchema, columns: list[str]) -> None:
        self._schema = schema
        self._columns = columns
        self._lookups = {c: self._build_lookup(c) for c in columns}

    def _build_lookup(self, column: str) -> dict[str, str]:
        spec = self._schema[column]
        lookup: dict[str, str] = {}
        for canonical in spec.categories:
            for key in (canonical, canonical.replace("-", " ")):
                lookup[_to_text(key)] = canonical
        for alias, canonical in spec.aliases.items():
            lookup[_to_text(alias)] = canonical
        # also accept the fully-squashed form: "family share" / "familyshare"
        lookup.update({re.sub(r"[^a-z0-9]", "", k): v for k, v in list(lookup.items())})
        return lookup

    def _canonical(self, column: str, value) -> str | float:
        text = _to_text(value)
        if text is None:
            return np.nan
        lookup = self._lookups[column]
        return lookup.get(text, lookup.get(re.sub(r"[^a-z0-9]", "", text), np.nan))

    def apply(self, df):
        changed = 0
        for col in self._columns:
            if col not in df:
                continue
            before = df[col].astype(object)
            after = before.map(lambda v, c=col: self._canonical(c, v))
            spec = self._schema[col]
            if spec.ftype is FeatureType.BINARY:
                after = after.map(lambda v: spec.categories.index(v) if isinstance(v, str) else np.nan).astype(float)
            else:
                after = after.astype(object)
            changed += _n_changed(before, after)
            df[col] = after
        return df, changed


class ParseDates(CleaningStep):
    """Try each known format; unparseable or *future* dates (relative to as-of) -> NaT."""

    name = "parse_dates"

    def __init__(self, column: str, as_of: str | pd.Timestamp, formats: tuple[str, ...] = DATE_FORMATS) -> None:
        self._col, self._as_of, self._formats = column, pd.Timestamp(as_of), formats

    def apply(self, df):
        if self._col not in df:
            return df, 0
        raw = df[self._col]
        if pd.api.types.is_datetime64_any_dtype(raw):
            parsed = raw
        else:
            text = raw.map(lambda v: v.strip() if isinstance(v, str) else v)
            parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
            for fmt in self._formats:
                parsed = parsed.fillna(pd.to_datetime(text, format=fmt, errors="coerce"))
        future = parsed > self._as_of
        df[self._col] = parsed.where(~future)
        return df, int(future.sum() + (parsed.isna() & raw.notna()).sum())


class EnforceValidRanges(CleaningStep):
    """Values outside the schema's physical domain are *invalid*, not outliers -> NaN."""

    name = "invalid_values_to_nan"

    def __init__(self, schema: DatasetSchema, columns: list[str]) -> None:
        self._schema, self._columns = schema, columns

    def apply(self, df):
        changed = 0
        for col in self._columns:
            if col not in df:
                continue
            spec = self._schema[col]
            bad = pd.Series(False, index=df.index)
            if spec.valid_min is not None:
                bad |= df[col] < spec.valid_min
            if spec.valid_max is not None:
                bad |= df[col] > spec.valid_max
            changed += int(bad.sum())
            df[col] = df[col].where(~bad)
        return df, changed


class DropDuplicateEntities(CleaningStep):
    """One row per customer. Must run BEFORE the split, or a customer can sit in train and test."""

    name = "drop_duplicate_entities"

    def __init__(self, id_column: str) -> None:
        self._col = id_column

    def apply(self, df):
        before = len(df)
        df = df.drop_duplicates(subset=[self._col], keep="first")
        return df, before - len(df)


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    changes: dict[str, int] = field(default_factory=dict)


class DataCleaner:
    """Runs an ordered chain of `CleaningStep`s and reports what each one did."""

    def __init__(self, steps: list[CleaningStep]) -> None:
        self._steps = steps

    def clean(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        report = CleaningReport(rows_in=len(df))
        out = df.copy()
        for step in self._steps:
            out, n = step.apply(out)
            report.changes[step.name] = n
        report.rows_out = len(out)
        return out.reset_index(drop=True), report

    @classmethod
    def _common_steps(cls, schema: DatasetSchema, as_of) -> list[CleaningStep]:
        numeric = schema.of_type(FeatureType.CONTINUOUS, FeatureType.DISCRETE)
        categorical = schema.of_type(FeatureType.NOMINAL, FeatureType.ORDINAL, FeatureType.BINARY)
        date_cols = schema.of_type(FeatureType.DATE)
        return [
            NormalizeNullTokens(),
            NormalizeIdentifier(schema.id_column),
            ParseNumeric(numeric),
            CanonicalizeCategories(schema, categorical),
            *[ParseDates(c, as_of) for c in date_cols],
            EnforceValidRanges(schema, numeric),
        ]

    @classmethod
    def for_training(cls, schema: DatasetSchema, snapshot_date: str) -> "DataCleaner":
        steps = cls._common_steps(schema, snapshot_date)
        steps.insert(2, ParseTarget(schema.target))
        steps.append(DropDuplicateEntities(schema.id_column))
        return cls(steps)

    @classmethod
    def for_inference(cls, schema: DatasetSchema, as_of: str | pd.Timestamp) -> "DataCleaner":
        """Same transformations, minus the label handling and the batch-level dedup."""
        return cls(cls._common_steps(schema, as_of))
