import numpy as np
import pytest

from churn.data.schema import MODELING_SCHEMA
from churn.features.preprocessing import TabularPreprocessor
from churn.features.selection import SELECTORS
from churn.features.transformers import IQRCapper
from churn.imbalance import IMBALANCE_STRATEGIES

FEATURES = ["contract_type", "payment_method", "tenure_months", "num_support_tickets", "satisfaction_score",
            "customer_tier", "is_paperless_billing", "days_since_last_active", "transaction_amount"]


def test_iqr_capper_learns_fences_from_fit_data_only():
    capper = IQRCapper(k=1.5).fit(np.array([[1.0], [2.0], [3.0], [4.0]]))
    assert capper.transform(np.array([[100.0]]))[0, 0] == pytest.approx(capper.upper_[0])


def test_preprocessor_is_fitted_on_train_and_handles_the_unseen(splits):
    pre = TabularPreprocessor(MODELING_SCHEMA, FEATURES).fit(splits.train.X)
    medians = pre._sanitizer._inner.named_transformers_["num"].named_steps["impute"].statistics_
    train_medians = splits.train.X[MODELING_SCHEMA.numeric(FEATURES)].median().to_numpy()
    np.testing.assert_allclose(medians, train_medians)

    weird = splits.val.X.head(3).copy()
    weird["contract_type"] = ["Prepaid", np.nan, "Unseen-Plan"]
    weird["tenure_months"] = [np.nan, 1e6, 3]
    out = pre.transform(weird)
    assert out.dtype == np.float32 and not np.isnan(out).any()
    assert out.shape[1] == len(pre.output_feature_names)


def test_hygiene_drops_leak_and_redundancy(splits):
    result = SELECTORS.create("hygiene", schema=MODELING_SCHEMA, seed=0).select(
        splits.train.X, splits.train.y, MODELING_SCHEMA.model_candidates())
    assert "exit_survey_score" in result.dropped and "leakage" in result.dropped["exit_survey_score"]
    assert "total_charges" in result.dropped and "redundant" in result.dropped["total_charges"]


def test_hybrid_selection_keeps_drivers_and_drops_noise(splits):
    result = SELECTORS.create("hybrid", schema=MODELING_SCHEMA, seed=0,
                              permutation={"n_splits": 3, "n_repeats": 3}).select(
        splits.train.X, splits.train.y, MODELING_SCHEMA.model_candidates())
    assert {"days_since_last_active", "num_support_tickets", "satisfaction_score"} <= set(result.selected)
    assert not {"region", "marketing_emails_opened", "exit_survey_score"} & set(result.selected)


@pytest.mark.parametrize("name", IMBALANCE_STRATEGIES.names)
def test_imbalance_strategies_only_touch_training_rows(name, splits):
    pre = TabularPreprocessor(MODELING_SCHEMA, FEATURES).fit_sanitizer(splits.train.X)
    sanitized = pre.sanitize(splits.train.X)
    balanced = IMBALANCE_STRATEGIES.create(name, seed=0).prepare(
        sanitized, splits.train.y, pre.categorical_columns(sanitized))
    assert list(balanced.X.columns) == list(sanitized.columns)
    assert 0 < balanced.effective_positive_rate < 1
    if name == "smotenc":
        assert balanced.X["contract_type"].isin(list(MODELING_SCHEMA["contract_type"].categories) + ["Missing"]).all()
        missing_cols = [c for c in balanced.X if c.startswith("missing_")]
        assert set(np.unique(balanced.X[missing_cols].to_numpy())) <= {0.0, 1.0}
