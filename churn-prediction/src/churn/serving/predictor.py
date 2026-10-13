"""Inference facade: raw customer records in, churn probabilities and decisions out.

    raw dicts -> DataCleaner.for_inference -> FeatureEngineer(as_of) -> fitted preprocessor
              -> InferenceBackend (torch | onnx) -> sigmoid -> threshold

The cleaning and feature code are the *same classes* used to build the training set, and
the preprocessor is the *same fitted object* — the two classic sources of train/serve skew
are removed by construction rather than by discipline.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from churn.common.registry import Registry
from churn.config import ArchitectureConfig
from churn.data.cleaning import DataCleaner
from churn.data.schema import RAW_SCHEMA
from churn.features.engineering import FeatureEngineer
from churn.modeling.networks import NETWORKS
from churn.serving.bundle import METADATA_FILE, PREPROCESSOR_FILE, BundleMetadata

BACKENDS: Registry["InferenceBackend"] = Registry("inference backend")


class InferenceBackend(ABC):
    @abstractmethod
    def logits(self, X: np.ndarray) -> np.ndarray: ...


@BACKENDS.register("torch")
class TorchBackend(InferenceBackend):
    def __init__(self, bundle_dir: Path, metadata: BundleMetadata) -> None:
        arch = dict(metadata.architecture)
        arch["hidden_dims"] = tuple(arch["hidden_dims"])
        self._model = NETWORKS.create(arch["name"], input_dim=metadata.input_dim, arch=ArchitectureConfig(**arch))
        state = torch.load(bundle_dir / metadata.artifacts["state_dict"], weights_only=True)
        self._model.load_state_dict(state)
        self._model.eval()

    @torch.no_grad()
    def logits(self, X):
        return self._model(torch.as_tensor(X, dtype=torch.float32)).numpy()


@BACKENDS.register("onnx")
class OnnxBackend(InferenceBackend):
    def __init__(self, bundle_dir: Path, metadata: BundleMetadata) -> None:
        import onnxruntime as ort

        self._session = ort.InferenceSession(str(bundle_dir / metadata.artifacts["onnx"]),
                                             providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name

    def logits(self, X):
        return self._session.run(None, {self._input: X.astype(np.float32)})[0].reshape(-1)


class ChurnPredictor:
    def __init__(self, preprocessor, backend: InferenceBackend, metadata: BundleMetadata) -> None:
        self._preprocessor = preprocessor
        self._backend = backend
        self._metadata = metadata

    @classmethod
    def load(cls, bundle_dir: str | Path, backend: str = "onnx") -> "ChurnPredictor":
        bundle_dir = Path(bundle_dir)
        metadata = BundleMetadata.from_json((bundle_dir / METADATA_FILE).read_text(encoding="utf-8"))
        preprocessor = joblib.load(bundle_dir / PREPROCESSOR_FILE)
        return cls(preprocessor, BACKENDS.create(backend, bundle_dir=bundle_dir, metadata=metadata), metadata)

    @property
    def metadata(self) -> BundleMetadata:
        return self._metadata

    @property
    def threshold(self) -> float:
        return self._metadata.threshold

    def _features(self, records: list[dict] | pd.DataFrame, as_of: str | pd.Timestamp | None) -> np.ndarray:
        as_of = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now().normalize()
        raw = pd.DataFrame(records) if not isinstance(records, pd.DataFrame) else records.copy()
        for col in RAW_SCHEMA.columns:  # tolerate absent optional fields; they'll be imputed
            if col not in raw and col != RAW_SCHEMA.target:
                raw[col] = np.nan
        cleaned, _ = DataCleaner.for_inference(RAW_SCHEMA, as_of).clean(raw)
        features = FeatureEngineer.default(as_of).transform(cleaned)
        return self._preprocessor.transform(features)

    def predict_proba(self, records, as_of=None) -> np.ndarray:
        logits = self._backend.logits(self._features(records, as_of))
        return 1.0 / (1.0 + np.exp(-logits))

    def predict(self, records, as_of=None) -> list[dict]:
        raw = pd.DataFrame(records) if not isinstance(records, pd.DataFrame) else records
        proba = self.predict_proba(raw, as_of)
        ids = raw.get(RAW_SCHEMA.id_column, pd.Series([None] * len(raw)))
        return [{"customer_id": cid, "churn_probability": round(float(p), 6), "will_churn": bool(p >= self.threshold),
                 "threshold": self.threshold, "model_version": self._metadata.version}
                for cid, p in zip(ids, proba)]

    def describe(self) -> str:
        return json.dumps({k: self._metadata.__dict__[k] for k in ("model_name", "version", "stage", "threshold")})
