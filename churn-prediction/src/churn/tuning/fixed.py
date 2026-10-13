from __future__ import annotations

from churn.tuning.base import TUNERS, HyperparameterTuner, TuningResult


@TUNERS.register("fixed")
class FixedHyperparameters(HyperparameterTuner):
    """VANILLA: use the hand-picked values from the config as-is (see notes/05)."""

    def __init__(self, **_) -> None:
        pass

    def tune(self, base, data, service):
        return TuningResult(spec=base, description="fixed hyper-parameters from config")
