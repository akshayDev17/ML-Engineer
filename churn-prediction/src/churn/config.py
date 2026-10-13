"""Typed run configuration.

The YAML file chooses *which* strategy implements each step (vanilla vs advanced) and with
what parameters; the CLI supplies only the two run-time knobs the brief asks for
(`--n-rows`, `--imbalance-ratio`). Dataclasses are frozen so a config can't be mutated
mid-run — the config that was logged is the config that ran.
"""
from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RunArgs:
    """The only two inputs accepted on the command line."""

    n_rows: int = 20_000
    imbalance_ratio: float = 9.0  # majority:minority, i.e. 9.0 -> 9 retained : 1 churner (10% churn)

    def __post_init__(self) -> None:
        if self.n_rows < 500:
            raise ValueError("n_rows must be >= 500 so that val/test still hold a few churners")
        if self.imbalance_ratio < 1.0:
            raise ValueError("imbalance_ratio is majority:minority and must be >= 1.0")

    @property
    def positive_rate(self) -> float:
        return 1.0 / (1.0 + self.imbalance_ratio)


@dataclass(frozen=True)
class PathsConfig:
    data_dir: str = "data"
    artifacts_dir: str = "artifacts"


@dataclass(frozen=True)
class DataConfig:
    generator: str = "pattern"  # vanilla: "random"
    snapshot_date: str = "2026-09-30"
    corruption_rate: float = 0.04  # base rate for each dirt type


@dataclass(frozen=True)
class SplitConfig:
    val_size: float = 0.15
    test_size: float = 0.15


@dataclass(frozen=True)
class FeatureSelectionConfig:
    strategy: str = "hybrid"  # hybrid | hygiene | mutual_info | permutation
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreprocessingConfig:
    scaler: str = "standard"  # standard | robust | minmax
    iqr_k: float = 3.0  # 3.0 => cap only "extreme" outliers (Tukey's outer fence)
    skew_threshold: float = 1.0


@dataclass(frozen=True)
class ImbalanceConfig:
    strategy: str = "class_weight"  # vanilla: "none"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArchitectureConfig:
    name: str = "mlp"  # mlp | residual_mlp
    hidden_dims: tuple[int, ...] = (64, 32)
    dropout: float = 0.3
    activation: str = "relu"
    batch_norm: bool = True


@dataclass(frozen=True)
class TrainingConfig:
    optimizer: str = "adamw"
    lr: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 256
    max_epochs: int = 100
    early_stopping_patience: int = 10
    lr_scheduler_factor: float = 0.5
    lr_scheduler_patience: int = 4
    grad_clip_norm: float = 1.0
    monitor: str = "val_pr_auc"  # what early stopping / LR scheduling watch on the val set


@dataclass(frozen=True)
class ModelConfig:
    architecture: ArchitectureConfig = field(default_factory=ArchitectureConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)


@dataclass(frozen=True)
class TuningConfig:
    strategy: str = "fixed"  # fixed | optuna
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThresholdConfig:
    policy: str = "max_fbeta"  # fixed | max_fbeta | min_recall
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServingConfig:
    model_name: str = "churn-model"
    exporters: tuple[str, ...] = ("state_dict", "onnx")


@dataclass(frozen=True)
class PipelineConfig:
    seed: int = 42
    device: str = "cpu"
    paths: PathsConfig = field(default_factory=PathsConfig)
    data: DataConfig = field(default_factory=DataConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    feature_selection: FeatureSelectionConfig = field(default_factory=FeatureSelectionConfig)
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    imbalance: ImbalanceConfig = field(default_factory=ImbalanceConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    tuning: TuningConfig = field(default_factory=TuningConfig)
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    serving: ServingConfig = field(default_factory=ServingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return _from_dict(cls, raw)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _from_dict(cls: type, raw: dict[str, Any]):
    """Recursively build a (frozen) dataclass from a plain dict, rejecting unknown keys."""
    hints = typing.get_type_hints(cls)
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    kwargs = {}
    for name, value in raw.items():
        hint = hints[name]
        if dataclasses.is_dataclass(hint) and isinstance(value, dict):
            kwargs[name] = _from_dict(hint, value)
        elif typing.get_origin(hint) is tuple and isinstance(value, list):
            kwargs[name] = tuple(value)
        else:
            kwargs[name] = value
    return cls(**kwargs)
