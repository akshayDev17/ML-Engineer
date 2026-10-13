from __future__ import annotations

import pandas as pd
import pytest

from churn.data.cleaning import DataCleaner
from churn.data.corruption import DirtyDataInjector
from churn.data.generators import GENERATORS
from churn.data.schema import RAW_SCHEMA
from churn.data.splitting import StratifiedSplitter
from churn.features.engineering import FeatureEngineer

SNAPSHOT = "2026-09-30"


@pytest.fixture(scope="session")
def clean_pattern_df() -> pd.DataFrame:
    return GENERATORS.create("pattern", snapshot_date=SNAPSHOT, seed=7).generate(6000, 0.1)


@pytest.fixture(scope="session")
def dirty_df(clean_pattern_df) -> pd.DataFrame:
    dirty, _ = DirtyDataInjector.default(RAW_SCHEMA, 0.05, SNAPSHOT, seed=7).inject(clean_pattern_df)
    # emulate the CSV round trip: everything becomes text
    return dirty.astype(object).where(dirty.notna(), "").astype(str)


@pytest.fixture(scope="session")
def cleaned_df(dirty_df) -> pd.DataFrame:
    cleaned, _ = DataCleaner.for_training(RAW_SCHEMA, SNAPSHOT).clean(dirty_df)
    return cleaned


@pytest.fixture(scope="session")
def splits(cleaned_df):
    df = FeatureEngineer.default(SNAPSHOT).transform(cleaned_df)
    X = df.drop(columns=["churn"]).set_index("customer_id")
    return StratifiedSplitter(0.15, 0.15, seed=7).split(X, df["churn"].set_axis(X.index))
