"""Decision-threshold policies, fitted on the VALIDATION split.

The network outputs a probability; the business acts on a yes/no. Where to cut is a
business decision (M10), and it must be chosen on data the model wasn't trained on and
that the final report isn't computed on — i.e. the validation split.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from sklearn.metrics import precision_recall_curve

from churn.common.registry import Registry

THRESHOLD_POLICIES: Registry["ThresholdPolicy"] = Registry("threshold policy")


class ThresholdPolicy(ABC):
    @abstractmethod
    def select(self, y_true: np.ndarray, proba: np.ndarray) -> float: ...

    def describe(self) -> str:
        return type(self).__name__


@THRESHOLD_POLICIES.register("fixed")
class FixedThreshold(ThresholdPolicy):
    """VANILLA: the default 0.5 cut (only sensible if probabilities are calibrated to the prior
    AND errors cost the same — rarely both true for churn)."""

    def __init__(self, value: float = 0.5, **_) -> None:
        self._value = value

    def select(self, y_true, proba):
        return self._value

    def describe(self):
        return f"fixed threshold {self._value}"


@THRESHOLD_POLICIES.register("max_fbeta")
class MaxFBetaThreshold(ThresholdPolicy):
    """Pick the threshold maximising F-beta on validation. beta=1 -> F1; beta=2 says a missed
    churner (FN) costs ~2x as much as a wasted retention offer (FP)."""

    def __init__(self, beta: float = 1.0, **_) -> None:
        self._beta = beta

    def select(self, y_true, proba):
        precision, recall, thresholds = precision_recall_curve(y_true, proba)
        p, r = precision[:-1], recall[:-1]  # last point has no threshold
        b2 = self._beta ** 2
        fbeta = np.where(p + r > 0, (1 + b2) * p * r / np.maximum(b2 * p + r, 1e-12), 0.0)
        return float(thresholds[int(np.argmax(fbeta))])

    def describe(self):
        return f"threshold maximising F{self._beta:g} on validation"


@THRESHOLD_POLICIES.register("min_recall")
class MinRecallThreshold(ThresholdPolicy):
    """Highest-precision threshold that still catches at least `target_recall` of churners
    (e.g. 'the retention team must reach 80% of would-be churners')."""

    def __init__(self, target_recall: float = 0.8, **_) -> None:
        self._target = target_recall

    def select(self, y_true, proba):
        precision, recall, thresholds = precision_recall_curve(y_true, proba)
        ok = np.flatnonzero(recall[:-1] >= self._target)
        if not len(ok):
            return float(thresholds[0])
        return float(thresholds[ok[np.argmax(precision[:-1][ok])]])

    def describe(self):
        return f"max precision subject to recall >= {self._target} on validation"
