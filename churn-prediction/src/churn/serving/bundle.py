"""The model bundle and a minimal local model registry (M9).

A model is never "a .pt file". It is an immutable, versioned directory:

    artifacts/registry/<model_name>/v<N>/
        model_state.pt        weights (framework-native, safe to load: weights_only)
        model.onnx            portable serving artifact
        preprocessor.joblib   the *fitted* two-stage preprocessor (imputers, caps, scalers, encoders)
        metadata.json         architecture, features, threshold, metrics, lineage, versions
        evaluation/           ROC / PR / training-curve figures

Everything needed to turn a raw customer record into a decision travels together, so the
serving process cannot pair the model with the wrong preprocessing or threshold.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from churn.features.preprocessing import TabularPreprocessor
from churn.modeling.networks import ChurnNetwork
from churn.serving.exporters import EXPORTERS

PREPROCESSOR_FILE = "preprocessor.joblib"
METADATA_FILE = "metadata.json"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_versions() -> dict[str, str]:
    import numpy, pandas, sklearn, torch  # noqa: E401  (local: only needed at save time)

    return {"python": platform.python_version(), "torch": torch.__version__, "sklearn": sklearn.__version__,
            "pandas": pandas.__version__, "numpy": numpy.__version__}


@dataclass
class BundleMetadata:
    model_name: str
    version: int
    architecture: dict[str, Any]
    input_dim: int
    selected_features: list[str]
    threshold: float
    as_of_date: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    stage: str = "candidate"  # candidate -> staging -> production -> archived (promotion is a separate act)
    lineage: dict[str, Any] = field(default_factory=dict)  # data hash, seed, config, git sha if available
    evaluation: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=library_versions)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=str)

    @classmethod
    def from_json(cls, text: str) -> "BundleMetadata":
        return cls(**json.loads(text))


class LocalModelRegistry:
    """Append-only, versioned storage. Versions are immutable once written."""

    def __init__(self, root: str | Path, model_name: str) -> None:
        self._dir = Path(root) / model_name
        self._dir.mkdir(parents=True, exist_ok=True)
        self._name = model_name

    def versions(self) -> list[int]:
        return sorted(int(p.name[1:]) for p in self._dir.glob("v*") if p.name[1:].isdigit())

    def latest_dir(self) -> Path:
        versions = self.versions()
        if not versions:
            raise FileNotFoundError(f"No registered versions under {self._dir}")
        return self._dir / f"v{versions[-1]}"

    def register(self, model: ChurnNetwork, preprocessor: TabularPreprocessor, metadata: BundleMetadata,
                 exporters: tuple[str, ...]) -> Path:
        version = (self.versions() or [0])[-1] + 1
        bundle_dir = self._dir / f"v{version}"
        bundle_dir.mkdir(parents=True, exist_ok=False)
        metadata.version = version
        metadata.model_name = self._name
        for name in exporters:
            path = EXPORTERS.create(name).export(model, bundle_dir)
            metadata.artifacts[name] = path.name
        joblib.dump(preprocessor, bundle_dir / PREPROCESSOR_FILE)
        metadata.artifacts["preprocessor"] = PREPROCESSOR_FILE
        (bundle_dir / METADATA_FILE).write_text(metadata.to_json(), encoding="utf-8")
        return bundle_dir
