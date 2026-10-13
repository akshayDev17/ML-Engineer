import numpy as np
import pytest
import torch

from churn.config import ArchitectureConfig, TrainingConfig
from churn.evaluation.thresholds import THRESHOLD_POLICIES
from churn.modeling import NETWORKS, ArrayDataset, ModelSpec, ModelTrainingService, TrainingData


@pytest.mark.parametrize("name", NETWORKS.names)
def test_networks_are_interchangeable(name):
    net = NETWORKS.create(name, input_dim=7, arch=ArchitectureConfig(name=name, hidden_dims=(16, 8)))
    net.init_output_bias(0.1)
    assert net(torch.randn(5, 7)).shape == (5,)
    assert torch.sigmoid(net.head.bias).item() == pytest.approx(0.1)


def test_training_learns_a_separable_signal_and_early_stops():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 5)).astype(np.float32)
    y = (X[:, 0] + 0.5 * X[:, 1] > 1.2).astype(np.float32)
    data = TrainingData(ArrayDataset(X[:1500], y[:1500]), ArrayDataset(X[1500:], y[1500:]),
                        effective_positive_rate=float(y.mean()))
    spec = ModelSpec(ArchitectureConfig(hidden_dims=(16,)), TrainingConfig(max_epochs=200, early_stopping_patience=5))
    _, state = ModelTrainingService(seed=0).train(spec, data, verbose=False)
    assert max(e.val_roc_auc for e in state.history) > 0.97
    assert len(state.history) < 200 and "early stop" in state.stop_reason


def test_threshold_policies():
    y = np.array([0, 0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.6, 0.7, 0.9])
    assert THRESHOLD_POLICIES.create("fixed").select(y, p) == 0.5
    assert THRESHOLD_POLICIES.create("max_fbeta", beta=1.0).select(y, p) == pytest.approx(0.7)
    assert THRESHOLD_POLICIES.create("min_recall", target_recall=1.0).select(y, p) == pytest.approx(0.7)
