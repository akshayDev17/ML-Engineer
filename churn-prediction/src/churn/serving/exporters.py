"""Model export strategies.

* `state_dict` — the framework-native artifact: weights only (no pickled code), reloaded
  with `torch.load(weights_only=True)` into an architecture rebuilt from metadata. This is
  the source of truth for re-training / fine-tuning and for torch-based serving.
* `onnx`       — the portable serving artifact (M12): framework-free, runs in ONNX Runtime
  with no autograd / Python overhead on the hot path. Exported with a dynamic batch axis.

(TorchScript is deliberately not offered: it is deprecated in current PyTorch in favour of
`torch.export`, which is exactly what the ONNX dynamo exporter is built on.)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import torch

from churn.common.registry import Registry
from churn.modeling.networks import ChurnNetwork

EXPORTERS: Registry["ModelExporter"] = Registry("model exporter")


class ModelExporter(ABC):
    filename: str

    @abstractmethod
    def export(self, model: ChurnNetwork, bundle_dir: Path) -> Path: ...


@EXPORTERS.register("state_dict")
class StateDictExporter(ModelExporter):
    filename = "model_state.pt"

    def export(self, model, bundle_dir):
        path = bundle_dir / self.filename
        torch.save(model.state_dict(), path)
        return path


@EXPORTERS.register("onnx")
class OnnxExporter(ModelExporter):
    filename = "model.onnx"

    def __init__(self, opset_version: int = 18) -> None:
        self._opset = opset_version

    def export(self, model, bundle_dir):
        for noisy in ("torch.onnx", "onnxscript", "onnx_ir"):  # exporter internals log at INFO
            logging.getLogger(noisy).setLevel(logging.ERROR)
        path = bundle_dir / self.filename
        model.eval()
        example = torch.zeros(2, model.input_dim, dtype=torch.float32)
        torch.onnx.export(
            model, (example,), str(path), input_names=["features"], output_names=["logit"],
            dynamo=True, dynamic_shapes={"x": {0: torch.export.Dim("batch")}},
            opset_version=self._opset, external_data=False, verbose=False,
        )
        return path
