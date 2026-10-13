# 08 · Saving the model for serving

## What is saved: a versioned bundle, not a `.pt` file

```
artifacts/registry/churn-model/v1/
├── model_state.pt        PyTorch state_dict: weights only (≈20 KB)
├── model.onnx            portable inference graph, dynamic batch axis (≈28 KB)
├── preprocessor.joblib   FITTED two-stage preprocessor: imputers, IQR caps, skew mask, scaler, encoders (≈16 KB)
├── metadata.json         architecture, input_dim, selected features, threshold, as-of date, stage,
│                         test/val metrics, lineage (raw-data SHA-256, seed, full config), library versions
├── run_summary.json      everything the run decided, including every dropped feature and the reason
└── evaluation/           roc_curve.png, pr_curve.png, training_curves.png, optuna_trials.csv
```

The bundle exists because **a model is only usable together with its exact preprocessing and decision threshold.** Shipping the weights without the fitted scaler, encoder, or imputation medians is the classic training/serving skew bug (M6). Shipping without the threshold silently reverts production to 0.5.

## Why each format

| artifact | role | why this format |
|---|---|---|
| `state_dict` | source of truth for retraining, fine-tuning, and torch serving | contains no pickled code; reloaded with `torch.load(..., weights_only=True)` into an architecture rebuilt from `metadata.architecture` through the same `NETWORKS` registry |
| **ONNX** | the production inference artifact | framework-free: runs in ONNX Runtime with no autograd or Python overhead. Exported with `torch.onnx.export(dynamo=True)` and a dynamic batch dimension (M12) |
| `preprocessor.joblib` | the fitted sklearn transformers | the native persistence for sklearn objects. Only load bundles you produced yourself: joblib is pickle |
| ~~TorchScript~~ | — | deprecated in current PyTorch in favour of `torch.export`, which the ONNX dynamo exporter already uses |
| ~~`torch.save(model)`~~ (Pima notebook) | — | pickles the class and module path; it breaks on refactors and needs arbitrary-code unpickling |

## The registry (M9)

`LocalModelRegistry` writes **immutable, monotonically numbered versions** (`v1`, `v2`, …), and the directory creation refuses to overwrite. Each version is registered as stage `candidate`. Promotion to `staging` / `production` is a separate, deliberate act. In a team setting the same metadata maps one-to-one onto an MLflow Model Registry entry: `mlflow.pytorch.log_model` plus registered model, stage, and tags. The local class is a stand-in so the project has no infrastructure dependency.

## Serving path: one code path for training and serving

```
raw JSON record
  → DataCleaner.for_inference(as_of)       the same parsing/canonicalisation classes as training
  → FeatureEngineer(as_of)                 days_since_last_active, measured from the request's as-of date
  → preprocessor.transform                 the fitted object from the bundle
  → InferenceBackend.logits                OnnxBackend (default) | TorchBackend (Strategy)
  → sigmoid → compare with metadata.threshold
```

```python
from churn.serving import ChurnPredictor
predictor = ChurnPredictor.load("artifacts/registry/churn-model/v1", backend="onnx")
predictor.predict([{"customer_id": "C-1", "contract_type": " PREPAID", "payment_method": "ewallet",
                    "tenure_months": "2 months", "num_support_tickets": 6, "satisfaction_score": "1",
                    "last_active_date": "02-Aug-2026", "transaction_amount": "$1,250.00"}],
                  as_of="2026-09-30")
# -> [{"customer_id": "C-1", "churn_probability": 0.998, "will_churn": True, "threshold": 0.705, "model_version": 1}]
```

Online endpoint (FastAPI; install the `serve` extra):

```bash
uv pip install -e ".[serve]"
CHURN_BUNDLE=artifacts/registry/churn-model/v1 uvicorn churn.serving.app:app --port 8000
curl -s localhost:8000/predict -H 'content-type: application/json' \
  -d '{"as_of":"2026-09-30","records":[{"customer_id":"C-1","contract_type":"Prepaid","tenure_months":2,"num_support_tickets":6,"satisfaction_score":"Very Dissatisfied","last_active_date":"2026-08-02"}]}'
```

The predictor is loaded **once at startup** (FastAPI `lifespan`), not per request. Every request field is optional: missing values flow into the same imputers used in training.

## Verified: serving parity

At the end of each run, the pipeline **reloads the bundle the way a server would** and re-scores every test customer from their cleaned *record* (not the training matrix), using both backends:

```
serving parity [torch]: max |p_served − p_pipeline| = 1.2e-07
serving parity [onnx]:  max |p_served − p_pipeline| = 1.2e-07
```

`tests/test_end_to_end.py` also scores deliberately dirty raw records (`"$1,250.00"`, `" PREPAID"`, `"2 months"`, `"02-Aug-2026"`) through both backends.

## What to watch after deployment (beyond this exercise)

- **As-of date.** Recency must be computed against the scoring time. The API takes `as_of` (default: today); batch scoring should pass the snapshot date explicitly.
- **Drift.** Monitor the 8 *selected* inputs (selection shrank the surface from 18) and the score distribution against the training reference (PSI, as in M5/M16).
- **Label delay.** Churn labels arrive 60 days late, so precision and recall can only be monitored with that lag. The score distribution and the input drift are the leading indicators.
