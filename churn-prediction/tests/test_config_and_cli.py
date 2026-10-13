import pytest

from churn.cli import DEFAULT_CONFIG, PROJECT_ROOT, parse_args
from churn.config import PipelineConfig, RunArgs


def test_cli_defaults_are_logical():
    args = parse_args([])
    assert args.n_rows == 20_000 and args.imbalance_ratio == 9.0
    assert args.positive_rate == pytest.approx(0.1)


def test_cli_accepts_only_the_two_arguments():
    assert parse_args(["--n-rows", "5000", "--imbalance-ratio", "19"]).positive_rate == pytest.approx(0.05)
    with pytest.raises(SystemExit):
        parse_args(["--epochs", "3"])


@pytest.mark.parametrize("bad", [{"n_rows": 10}, {"imbalance_ratio": 0.5}])
def test_run_args_validation(bad):
    with pytest.raises(ValueError):
        RunArgs(**bad)


@pytest.mark.parametrize("profile", ["advanced.yaml", "vanilla.yaml"])
def test_profiles_load(profile):
    cfg = PipelineConfig.from_yaml(PROJECT_ROOT / "configs" / profile)
    assert cfg.model.architecture.hidden_dims == (64, 32)


def test_unknown_config_key_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(DEFAULT_CONFIG.read_text() + "\nlearning_rate: 0.1\n")
    with pytest.raises(ValueError, match="Unknown keys"):
        PipelineConfig.from_yaml(bad)
