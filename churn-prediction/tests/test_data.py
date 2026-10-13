import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from churn.data.cleaning import DataCleaner
from churn.data.generators import GENERATORS
from churn.data.schema import RAW_SCHEMA, FeatureType

from conftest import SNAPSHOT


@pytest.mark.parametrize("name", ["random", "pattern"])
@pytest.mark.parametrize("rate", [0.05, 0.2])
def test_generators_honour_imbalance_ratio(name, rate):
    df = GENERATORS.create(name, snapshot_date=SNAPSHOT, seed=1).generate(20_000, rate)
    assert list(df.columns) == RAW_SCHEMA.columns
    assert df["churn"].mean() == pytest.approx(rate, abs=0.01)


def test_generation_is_deterministic():
    make = lambda: GENERATORS.create("pattern", snapshot_date=SNAPSHOT, seed=3).generate(1000, 0.1)  # noqa: E731
    pd.testing.assert_frame_equal(make(), make())


def test_pattern_generator_has_signal_and_random_has_none(clean_pattern_df):
    recency = (pd.Timestamp(SNAPSHOT) - pd.to_datetime(clean_pattern_df["last_active_date"])).dt.days
    assert roc_auc_score(clean_pattern_df["churn"], recency) > 0.6
    rnd = GENERATORS.create("random", snapshot_date=SNAPSHOT, seed=7).generate(6000, 0.1)
    rnd_recency = (pd.Timestamp(SNAPSHOT) - pd.to_datetime(rnd["last_active_date"])).dt.days
    assert abs(roc_auc_score(rnd["churn"], rnd_recency) - 0.5) < 0.05


def test_dirty_data_is_actually_dirty(dirty_df):
    assert dirty_df["customer_id"].str.strip().str.upper().duplicated().any()
    assert not dirty_df["contract_type"].isin(RAW_SCHEMA["contract_type"].categories + ("",)).all()
    assert dirty_df["transaction_amount"].str.contains(r"\$|USD", regex=True).any()
    assert dirty_df["churn"].isin(["Yes", "churned", "TRUE"]).any()


def test_cleaning_produces_contract_compliant_data(cleaned_df):
    assert set(cleaned_df["churn"].unique()) <= {0, 1}
    assert not cleaned_df["customer_id"].duplicated().any()
    for col in RAW_SCHEMA.of_type(FeatureType.NOMINAL, FeatureType.ORDINAL):
        assert set(cleaned_df[col].dropna()) <= set(RAW_SCHEMA[col].categories), col
    assert set(cleaned_df["is_paperless_billing"].dropna()) <= {0.0, 1.0}
    assert (cleaned_df["last_active_date"].dropna() <= pd.Timestamp(SNAPSHOT)).all()
    for col in RAW_SCHEMA.of_type(FeatureType.CONTINUOUS, FeatureType.DISCRETE):
        spec, values = RAW_SCHEMA[col], cleaned_df[col].dropna()
        assert pd.api.types.is_float_dtype(cleaned_df[col])
        if spec.valid_min is not None:
            assert (values >= spec.valid_min).all(), col
        if spec.valid_max is not None:
            assert (values <= spec.valid_max).all(), col


def test_cleaning_is_idempotent(cleaned_df):
    again, report = DataCleaner.for_training(RAW_SCHEMA, SNAPSHOT).clean(cleaned_df)
    pd.testing.assert_frame_equal(again, cleaned_df)
    assert sum(report.changes.values()) == 0


def test_splits_are_stratified_and_disjoint(splits):
    rates = [s.positive_rate for s in (splits.train, splits.val, splits.test)]
    assert np.ptp(rates) < 0.01
    ids = [set(s.X.index) for s in (splits.train, splits.val, splits.test)]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
