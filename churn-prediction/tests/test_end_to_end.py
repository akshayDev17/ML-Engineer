"""Small but complete run: data -> bundle -> reload as a server would -> score raw dirty records."""
from dataclasses import replace

import pytest

from churn.cli import DEFAULT_CONFIG
from churn.config import PipelineConfig, RunArgs, TuningConfig
from churn.factory import build_components
from churn.pipeline import ChurnPipeline
from churn.serving import ChurnPredictor


@pytest.fixture(scope="module")
def run_result(tmp_path_factory):
    root = tmp_path_factory.mktemp("run")
    cfg = PipelineConfig.from_yaml(DEFAULT_CONFIG)
    cfg = replace(cfg,
                  tuning=TuningConfig("optuna", {"n_trials": 3, "max_epochs_per_trial": 4, "n_startup_trials": 1,
                                                 "n_warmup_steps": 1}),
                  model=replace(cfg.model, training=replace(cfg.model.training, max_epochs=8)),
                  feature_selection=replace(cfg.feature_selection, params={
                      **cfg.feature_selection.params, "permutation": {"n_splits": 3, "n_repeats": 2}}))
    return ChurnPipeline(cfg, build_components(cfg, root)).run(RunArgs(n_rows=3000, imbalance_ratio=9))


def test_bundle_is_complete(run_result):
    files = {p.name for p in run_result.bundle_dir.iterdir()}
    assert {"model_state.pt", "model.onnx", "preprocessor.joblib", "metadata.json", "run_summary.json"} <= files
    assert {"roc_curve.png", "pr_curve.png", "training_curves.png"} <= {
        p.name for p in (run_result.bundle_dir / "evaluation").iterdir()}


def test_model_beats_no_skill_on_test(run_result):
    r = run_result.test_report
    assert r.roc_auc > 0.7 and r.pr_auc > 2 * r.no_skill_pr_auc


def test_serving_reproduces_pipeline_scores(run_result):
    assert max(run_result.summary["serving_parity"].values()) < 1e-5


@pytest.mark.parametrize("backend", ["torch", "onnx"])
def test_predictor_scores_raw_dirty_records(run_result, backend):
    predictor = ChurnPredictor.load(run_result.bundle_dir, backend)
    records = [
        {"customer_id": " cust-1 ", "transaction_amount": "$1,250.00", "contract_type": " PREPAID",
         "payment_method": "ewallet", "last_active_date": "02-Aug-2026", "tenure_months": "2 months",
         "num_support_tickets": 6, "satisfaction_score": "1", "is_paperless_billing": "Y"},
        {"customer_id": "CUST-2", "contract_type": "Business", "payment_method": "Bank Transfer",
         "last_active_date": "2026-09-29", "tenure_months": 60, "num_support_tickets": 0,
         "satisfaction_score": "Very Satisfied", "discount_pct": 20},
    ]
    out = predictor.predict(records, as_of="2026-09-30")
    assert [o["customer_id"] for o in out] == [" cust-1 ", "CUST-2"]
    assert out[0]["churn_probability"] > out[1]["churn_probability"]


def test_http_endpoint(run_result, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("CHURN_BUNDLE", str(run_result.bundle_dir))
    from churn.serving.app import app

    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        body = {"as_of": "2026-09-30", "records": [{"customer_id": "C-1", "contract_type": "Prepaid",
                                                     "last_active_date": "2026-08-02"}]}
        (pred,) = client.post("/predict", json=body).json()["predictions"]
        assert 0.0 <= pred["churn_probability"] <= 1.0 and pred["customer_id"] == "C-1"
