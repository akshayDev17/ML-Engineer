"""Command-line entry point.

Exactly two run-time arguments, as the brief requires:

    python -m churn [--n-rows 20000] [--imbalance-ratio 9]

`--imbalance-ratio` is majority:minority (9 -> 9 retained customers per churner, i.e. 10% churn).
Which implementation runs at each step (vanilla vs advanced) is configuration, not a CLI
flag: set CHURN_CONFIG to a YAML file (default: configs/advanced.yaml).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from churn.common.logging import get_logger
from churn.config import PipelineConfig, RunArgs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "advanced.yaml"


def parse_args(argv: list[str] | None = None) -> RunArgs:
    defaults = RunArgs()
    parser = argparse.ArgumentParser(prog="churn", description="Train and package a churn-prediction MLP.")
    parser.add_argument("--n-rows", type=int, default=defaults.n_rows,
                        help=f"rows of synthetic data to generate (default {defaults.n_rows})")
    parser.add_argument("--imbalance-ratio", type=float, default=defaults.imbalance_ratio,
                        help=f"majority:minority class ratio, >= 1 (default {defaults.imbalance_ratio:g} -> "
                             f"{100 * defaults.positive_rate:.0f}%% churn)")
    ns = parser.parse_args(argv)
    try:
        return RunArgs(n_rows=ns.n_rows, imbalance_ratio=ns.imbalance_ratio)
    except ValueError as exc:
        parser.error(str(exc))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(os.environ.get("CHURN_CONFIG", DEFAULT_CONFIG))
    config = PipelineConfig.from_yaml(config_path)
    log = get_logger("churn")
    log.info("config %s | n_rows=%d imbalance_ratio=%g (churn rate %.1f%%)", config_path.name, args.n_rows,
             args.imbalance_ratio, 100 * args.positive_rate)

    # Imported late so `--help` stays instant (torch/sklearn imports take a few seconds).
    from churn.factory import build_components
    from churn.pipeline import ChurnPipeline

    result = ChurnPipeline(config, build_components(config, PROJECT_ROOT)).run(args)
    r = result.test_report
    print("\n=== TEST SET (threshold chosen on validation) ===")
    print(f"precision {r.precision:.3f} | recall {r.recall:.3f} | F1 {r.f1:.3f} | ROC-AUC {r.roc_auc:.3f} | "
          f"PR-AUC {r.pr_auc:.3f} (no-skill {r.no_skill_pr_auc:.3f}) | threshold {r.threshold:.3f}")
    print(f"bundle: {result.bundle_dir}")
    return 0
