"""Network architectures (inheritance + polymorphism).

`ChurnNetwork` is the abstract contract: map a float matrix (B, d) to one raw logit per row.
Concrete subclasses differ only in how they build the hidden representation, so the
trainer, tuner, exporter and predictor work with any of them unchanged (Liskov).

Why one logit + BCEWithLogitsLoss instead of two logits + CrossEntropy (as in the Pima
notebook)? For binary targets they are equivalent in expressiveness, but the single logit
halves the head, gives `pos_weight` for class weighting for free, and fuses sigmoid+log for
numerical stability.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

import torch
from torch import nn

from churn.common.registry import Registry
from churn.config import ArchitectureConfig

NETWORKS: Registry["ChurnNetwork"] = Registry("network")

ACTIVATIONS: dict[str, type[nn.Module]] = {
    "relu": nn.ReLU, "gelu": nn.GELU, "silu": nn.SiLU, "leaky_relu": nn.LeakyReLU,
}


class ChurnNetwork(nn.Module, ABC):
    def __init__(self, input_dim: int, arch: ArchitectureConfig) -> None:
        super().__init__()
        if arch.activation not in ACTIVATIONS:
            raise KeyError(f"Unknown activation '{arch.activation}'. Available: {sorted(ACTIVATIONS)}")
        self._input_dim = input_dim
        self._arch = arch
        self.body = self._build_body()
        self.head = nn.Linear(self._body_output_dim(), 1)

    # ------------------------------------------------------------------ template hooks
    @abstractmethod
    def _build_body(self) -> nn.Module: ...

    @abstractmethod
    def _body_output_dim(self) -> int: ...

    # ------------------------------------------------------------------ shared behaviour
    @property
    def input_dim(self) -> int:
        return self._input_dim

    @property
    def architecture(self) -> ArchitectureConfig:
        return self._arch

    def _activation(self) -> nn.Module:
        return ACTIVATIONS[self._arch.activation]()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.body(x)).squeeze(-1)

    @torch.no_grad()
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        self.eval()
        return torch.sigmoid(self.forward(x))

    def init_output_bias(self, positive_rate: float) -> None:
        """Start from the (effective) class prior instead of p=0.5: removes the first epochs'
        'hockey-stick' loss where the net only learns the base rate."""
        p = min(max(positive_rate, 1e-4), 1 - 1e-4)
        nn.init.constant_(self.head.bias, math.log(p / (1 - p)))

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


@NETWORKS.register("mlp")
class MLPChurnNet(ChurnNetwork):
    """[Linear -> BatchNorm -> activation -> Dropout] x len(hidden_dims) -> Linear(1)."""

    def _build_body(self) -> nn.Module:
        layers: list[nn.Module] = []
        width = self._input_dim
        for hidden in self._arch.hidden_dims:
            layers.append(nn.Linear(width, hidden))
            if self._arch.batch_norm:
                layers.append(nn.BatchNorm1d(hidden))
            layers += [self._activation(), nn.Dropout(self._arch.dropout)]
            width = hidden
        return nn.Sequential(*layers)

    def _body_output_dim(self) -> int:
        return self._arch.hidden_dims[-1] if self._arch.hidden_dims else self._input_dim


class _ResidualBlock(nn.Module):
    def __init__(self, width: int, dropout: float, batch_norm: bool, activation: nn.Module) -> None:
        super().__init__()
        norm = nn.BatchNorm1d(width) if batch_norm else nn.Identity()
        self.block = nn.Sequential(norm, activation, nn.Dropout(dropout), nn.Linear(width, width))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


@NETWORKS.register("residual_mlp")
class ResidualMLPChurnNet(ChurnNetwork):
    """Stem Linear(d -> w), then len(hidden_dims) pre-norm residual blocks of width w = hidden_dims[0].
    Skip connections keep gradients healthy if the tuner picks a deeper net."""

    def _build_body(self) -> nn.Module:
        width = self._arch.hidden_dims[0]
        blocks = [_ResidualBlock(width, self._arch.dropout, self._arch.batch_norm, self._activation())
                  for _ in self._arch.hidden_dims]
        return nn.Sequential(nn.Linear(self._input_dim, width), *blocks, self._activation())

    def _body_output_dim(self) -> int:
        return self._arch.hidden_dims[0]
