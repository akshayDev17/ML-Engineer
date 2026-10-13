"""Composition root: the ONLY place that maps config strings to concrete classes.

Everything else depends on abstractions (`ChurnDataGenerator`, `FeatureSelector`,
`ImbalanceStrategy`, `HyperparameterTuner`, `ThresholdPolicy`, ...) and receives its
collaborators through constructors (Dependency Inversion). Swapping vanilla <-> advanced
is therefore a YAML edit, never a code edit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from churn.config import PipelineConfig
from churn.data.cleaning import DataCleaner
from churn.data.corruption import DirtyDataInjector
from churn.data.generators import GENERATORS, ChurnDataGenerator
from churn.data.repository import CsvDatasetRepository
from churn.data.schema import MODELING_SCHEMA, RAW_SCHEMA, DatasetSchema
from churn.data.splitting import DataSplitter, StratifiedSplitter
from churn.evaluation import THRESHOLD_POLICIES, ClassificationEvaluator, EvaluationPlotter, ThresholdPolicy
from churn.features.engineering import FeatureEngineer
from churn.features.selection import SELECTORS, FeatureSelector
from churn.imbalance import IMBALANCE_STRATEGIES, ImbalanceStrategy
from churn.modeling.service import ModelSpec, ModelTrainingService
from churn.serving.bundle import LocalModelRegistry
from churn.tuning import TUNERS, HyperparameterTuner


@dataclass(frozen=True)
class PipelineComponents:
    raw_schema: DatasetSchema
    modeling_schema: DatasetSchema
    generator: ChurnDataGenerator
    injector: DirtyDataInjector
    repository: CsvDatasetRepository
    cleaner: DataCleaner
    engineer: FeatureEngineer
    splitter: DataSplitter
    selector: FeatureSelector
    imbalance: ImbalanceStrategy
    tuner: HyperparameterTuner
    threshold_policy: ThresholdPolicy
    training_service: ModelTrainingService
    evaluator: ClassificationEvaluator
    model_registry: LocalModelRegistry
    plotter_factory: type[EvaluationPlotter]
    base_spec: ModelSpec


def build_components(cfg: PipelineConfig, project_root: Path) -> PipelineComponents:
    seed = cfg.seed
    snapshot = cfg.data.snapshot_date
    data_dir = project_root / cfg.paths.data_dir
    artifacts = project_root / cfg.paths.artifacts_dir
    return PipelineComponents(
        raw_schema=RAW_SCHEMA,
        modeling_schema=MODELING_SCHEMA,
        generator=GENERATORS.create(cfg.data.generator, snapshot_date=snapshot, seed=seed),
        injector=DirtyDataInjector.default(RAW_SCHEMA, cfg.data.corruption_rate, snapshot, seed),
        repository=CsvDatasetRepository(data_dir),
        cleaner=DataCleaner.for_training(RAW_SCHEMA, snapshot),
        engineer=FeatureEngineer.default(snapshot),
        splitter=StratifiedSplitter(cfg.split.val_size, cfg.split.test_size, seed),
        selector=SELECTORS.create(cfg.feature_selection.strategy, schema=MODELING_SCHEMA, seed=seed,
                                  **cfg.feature_selection.params),
        imbalance=IMBALANCE_STRATEGIES.create(cfg.imbalance.strategy, seed=seed, **cfg.imbalance.params),
        tuner=TUNERS.create(cfg.tuning.strategy, seed=seed, **cfg.tuning.params),
        threshold_policy=THRESHOLD_POLICIES.create(cfg.threshold.policy, **cfg.threshold.params),
        training_service=ModelTrainingService(cfg.device, seed),
        evaluator=ClassificationEvaluator(),
        model_registry=LocalModelRegistry(artifacts / "registry", cfg.serving.model_name),
        plotter_factory=EvaluationPlotter,
        base_spec=ModelSpec(cfg.model.architecture, cfg.model.training),
    )
