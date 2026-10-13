"""End-to-end orchestration. Each stage is one method; the order encodes the leakage rules:

    1 data      generate -> dirty -> persist raw CSV -> reload as text -> clean -> engineer
                (stateless steps only, so running them before the split is safe)
    2 split     stratified train / val / test        <- nothing below sees test until step 7
    3 select    feature selection on TRAIN only
    4 prepare   fit preprocessing on TRAIN; rebalance TRAIN only; encode val/test with train stats
    5 tune      choose hyper-parameters on VAL (fixed or Optuna)
    6 train     final fit on TRAIN, early stopping + LR schedule on VAL
    7 evaluate  threshold chosen on VAL, metrics + curves on TEST (touched exactly once)
    8 package   versioned bundle (weights, ONNX, preprocessor, metadata) + serving parity check
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from churn.common.logging import get_logger
from churn.common.reproducibility import seed_everything
from churn.config import PipelineConfig, RunArgs
from churn.data.splitting import DataSplits
from churn.evaluation.metrics import ClassificationReport
from churn.factory import PipelineComponents
from churn.features.preprocessing import TabularPreprocessor
from churn.features.selection import SelectionResult
from churn.modeling.service import ModelSpec, TrainingData
from churn.modeling.trainer import ArrayDataset, predict_proba
from churn.serving.bundle import BundleMetadata, file_sha256
from churn.serving.predictor import ChurnPredictor

log = get_logger("churn.pipeline")


@dataclass
class RunResult:
    bundle_dir: Path
    test_report: ClassificationReport
    test_report_at_default: ClassificationReport
    selection: SelectionResult
    spec: ModelSpec
    summary: dict = field(default_factory=dict)


class ChurnPipeline:
    def __init__(self, config: PipelineConfig, components: PipelineComponents) -> None:
        self._cfg = config
        self._c = components

    # ================================================================== public
    def run(self, args: RunArgs) -> RunResult:
        seed_everything(self._cfg.seed)
        engineered, raw_path, data_summary = self._stage_data(args)
        splits = self._stage_split(engineered)
        selection = self._stage_select(splits)
        preprocessor, training_data, balance_note = self._stage_prepare(splits, selection.selected)
        tuning = self._stage_tune(training_data)
        model, state, best_epoch = self._stage_train(tuning.spec, training_data)

        val_proba = predict_proba(model, training_data.val.X)
        threshold = self._c.threshold_policy.select(training_data.val.y, val_proba)
        test_X = preprocessor.transform(splits.test.X)
        test_proba = predict_proba(model, test_X)
        report = self._c.evaluator.evaluate(splits.test.y.to_numpy(), test_proba, threshold)
        report_default = self._c.evaluator.evaluate(splits.test.y.to_numpy(), test_proba, 0.5)
        log.info("TEST @ %s\n%s", self._c.threshold_policy.describe(), report.pretty())
        log.info("TEST @ 0.5 (for comparison)\n%s", report_default.pretty())

        summary = {
            "run_args": asdict(args), "data": data_summary, "splits": splits.summary(),
            "feature_selection": {"selected": selection.selected, "dropped": selection.dropped,
                                  "scores": selection.scores},
            "imbalance": balance_note, "tuning": tuning.description, "best_val_score": tuning.best_val_score,
            "spec": {"architecture": asdict(tuning.spec.architecture), "training": asdict(tuning.spec.training)},
            "training": {"epochs_run": len(state.history), "best_epoch": best_epoch, "stop_reason": state.stop_reason},
            "threshold": {"policy": self._c.threshold_policy.describe(), "value": threshold},
            "test": report.to_dict(), "test_at_0.5": report_default.to_dict(),
            "val": self._c.evaluator.evaluate(training_data.val.y, val_proba, threshold).to_dict(),
        }
        bundle_dir = self._stage_package(model, preprocessor, tuning.spec, selection, threshold, raw_path, summary)
        plotter = self._c.plotter_factory(bundle_dir / "evaluation")
        plotter.roc_curve(splits.test.y, test_proba, report.roc_auc, threshold)
        plotter.pr_curve(splits.test.y, test_proba, report.pr_auc, threshold)
        plotter.training_curves(state.history, best_epoch)
        if tuning.trials is not None:
            tuning.trials.to_csv(bundle_dir / "evaluation" / "optuna_trials.csv", index=False)

        summary["serving_parity"] = self._check_serving_parity(bundle_dir, splits, test_proba)
        (bundle_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        return RunResult(bundle_dir, report, report_default, selection, tuning.spec, summary)

    # ================================================================== stages
    def _stage_data(self, args: RunArgs) -> tuple[pd.DataFrame, Path, dict]:
        c = self._c
        clean = c.generator.generate(args.n_rows, args.positive_rate)
        dirty, corruption = c.injector.inject(clean)
        c.repository.save(clean, "churn_clean_groundtruth")
        raw_path = c.repository.save(dirty, "churn_raw")
        log.info("generated %d rows (%s, churn rate %.3f) -> dirtied to %d rows: %s", len(clean),
                 type(c.generator).__name__, clean[c.raw_schema.target].mean(), len(dirty), corruption.counts)

        raw = c.repository.load_raw("churn_raw")  # schema-on-read: everything is text
        cleaned, cleaning = c.cleaner.clean(raw)
        c.repository.save(cleaned, "churn_cleaned")
        log.info("cleaned %d -> %d rows: %s", cleaning.rows_in, cleaning.rows_out, cleaning.changes)
        engineered = c.engineer.transform(cleaned)
        return engineered, raw_path, {
            "generator": type(c.generator).__name__, "rows_generated": len(clean),
            "rows_raw": len(dirty), "rows_clean": len(cleaned), "corruption": corruption.counts,
            "cleaning": cleaning.changes, "churn_rate_clean": round(float(cleaned[c.raw_schema.target].mean()), 4),
        }

    def _stage_split(self, df: pd.DataFrame) -> DataSplits:
        target, id_col = self._c.raw_schema.target, self._c.raw_schema.id_column
        X = df.drop(columns=[target]).set_index(id_col)
        splits = self._c.splitter.split(X, df[target].set_axis(X.index))
        log.info("split: %s", splits.summary())
        return splits

    def _stage_select(self, splits: DataSplits) -> SelectionResult:
        candidates = self._c.modeling_schema.model_candidates()
        result = self._c.selector.select(splits.train.X, splits.train.y, candidates)
        log.info("feature selection kept %d/%d: %s", len(result.selected), len(candidates), result.selected)
        for name, reason in result.dropped.items():
            log.info("  dropped %-24s %s", name, reason)
        return result

    def _stage_prepare(self, splits: DataSplits, features: list[str]) -> tuple[TabularPreprocessor, TrainingData, str]:
        pp = self._cfg.preprocessing
        preprocessor = TabularPreprocessor(self._c.modeling_schema, features, pp.scaler, pp.iqr_k, pp.skew_threshold)
        train_sanitized = preprocessor.fit_sanitizer(splits.train.X).sanitize(splits.train.X)
        # The encoder (scaler/one-hot) is fitted on REAL training rows, before any synthetic rows exist.
        preprocessor.fit_encoder(train_sanitized)
        balanced = self._c.imbalance.prepare(train_sanitized, splits.train.y,
                                             preprocessor.categorical_columns(train_sanitized))
        log.info("imbalance: %s -> %d train rows, positive rate %.3f (effective %.3f)", balanced.description,
                 len(balanced.y), balanced.positive_rate, balanced.effective_positive_rate)
        data = TrainingData(
            train=ArrayDataset(preprocessor.encode(balanced.X), np.asarray(balanced.y, dtype=np.float32)),
            val=ArrayDataset(preprocessor.transform(splits.val.X), splits.val.y.to_numpy(np.float32)),
            pos_weight=balanced.pos_weight, sample_weights=balanced.sample_weights,
            effective_positive_rate=balanced.effective_positive_rate,
        )
        log.info("encoded matrix: %d features -> %d network inputs", len(features), data.input_dim)
        return preprocessor, data, balanced.description

    def _stage_tune(self, data: TrainingData):
        result = self._c.tuner.tune(self._c.base_spec, data, self._c.training_service)
        log.info("tuning: %s", result.description)
        return result

    def _stage_train(self, spec: ModelSpec, data: TrainingData):
        log.info("training %s %s | %s", spec.architecture.name, spec.architecture.hidden_dims, spec.training)
        model, state = self._c.training_service.train(spec, data)
        monitor = spec.training.monitor
        pick = max if not monitor.endswith("loss") else min
        best_epoch = pick(state.history, key=lambda e: e.metric(monitor)).epoch
        log.info("network has %d trainable parameters; best epoch %d", model.n_parameters(), best_epoch)
        return model, state, best_epoch

    def _stage_package(self, model, preprocessor, spec, selection, threshold, raw_path, summary) -> Path:
        metadata = BundleMetadata(
            model_name=self._cfg.serving.model_name, version=0,
            architecture=asdict(spec.architecture), input_dim=model.input_dim,
            selected_features=selection.selected, threshold=threshold, as_of_date=self._cfg.data.snapshot_date,
            lineage={"raw_data_sha256": file_sha256(raw_path), "seed": self._cfg.seed,
                     "config": self._cfg.to_dict(), "run_args": summary["run_args"],
                     "training_spec": asdict(spec.training)},
            evaluation={"test": summary["test"], "val": summary["val"], "threshold_policy": summary["threshold"]},
        )
        bundle_dir = self._c.model_registry.register(model, preprocessor, metadata, self._cfg.serving.exporters)
        log.info("registered bundle %s", bundle_dir)
        return bundle_dir

    def _check_serving_parity(self, bundle_dir: Path, splits: DataSplits, expected: np.ndarray) -> dict:
        """Reload the bundle exactly as a server would and re-score the test customers from their
        cleaned-but-not-engineered records; every backend must reproduce the in-pipeline scores."""
        id_col, target = self._c.raw_schema.id_column, self._c.raw_schema.target
        cleaned_raw = self._c.repository.load("churn_cleaned").set_index(id_col)
        records = cleaned_raw.loc[splits.test.X.index].drop(columns=[target]).reset_index()
        result = {}
        for backend in ("torch", "onnx") if "onnx" in self._cfg.serving.exporters else ("torch",):
            served = ChurnPredictor.load(bundle_dir, backend).predict_proba(records, as_of=self._cfg.data.snapshot_date)
            result[backend] = float(np.max(np.abs(served - expected)))
            log.info("serving parity [%s]: max |p_served - p_pipeline| = %.2e", backend, result[backend])
        return result
