"""A tiny generic registry: the backbone of the Open/Closed principle in this codebase.

Every swappable component (generator, selector, imbalance strategy, tuner, ...) registers
itself under a string key. The composition root (`churn.factory`) only ever asks a registry
for "the thing called X" — adding a new strategy means adding a new class with a decorator,
never editing an `if/elif` ladder.
"""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._builders: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        def decorator(builder: Callable[..., T]) -> Callable[..., T]:
            if name in self._builders:
                raise KeyError(f"{self._kind} '{name}' is already registered")
            self._builders[name] = builder
            return builder

        return decorator

    def create(self, name: str, **kwargs) -> T:
        try:
            builder = self._builders[name]
        except KeyError:
            raise KeyError(
                f"Unknown {self._kind} '{name}'. Available: {sorted(self._builders)}"
            ) from None
        return builder(**kwargs)

    def get(self, name: str) -> Callable[..., T]:
        return self._builders[name]

    @property
    def names(self) -> list[str]:
        return sorted(self._builders)

    def __contains__(self, name: str) -> bool:
        return name in self._builders
