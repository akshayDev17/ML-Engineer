"""Test-set evaluation for an imbalanced binary classifier.

Reported: precision, recall, F1 (at the chosen threshold), ROC-AUC and PR-AUC (threshold-
free, computed from *probabilities*, never from hard labels), Brier score, the confusion
matrix, and the no-skill baselines that make each number interpretable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)


@dataclass(frozen=True)
class ClassificationReport:
    threshold: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier: float
    brier_skill_score: float
    tn: int
    fp: int
    fn: int
    tp: int
    support_pos: int
    support_neg: int
    no_skill_pr_auc: float  # = prevalence: what a random scorer gets

    def to_dict(self) -> dict:
        return asdict(self)

    def pretty(self) -> str:
        return (f"threshold={self.threshold:.3f}  precision={self.precision:.3f}  recall={self.recall:.3f}  "
                f"f1={self.f1:.3f}  roc_auc={self.roc_auc:.3f}  pr_auc={self.pr_auc:.3f} "
                f"(no-skill {self.no_skill_pr_auc:.3f})  brier={self.brier:.4f}\n"
                f"confusion matrix [[TN FP] [FN TP]] = [[{self.tn} {self.fp}] [{self.fn} {self.tp}]]")


class ClassificationEvaluator:
    def evaluate(self, y_true: np.ndarray, proba: np.ndarray, threshold: float) -> ClassificationReport:
        y_true = np.asarray(y_true).astype(int)
        y_pred = (proba >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        prevalence = float(y_true.mean())
        brier = float(brier_score_loss(y_true, proba))
        brier_ref = float(brier_score_loss(y_true, np.full_like(proba, prevalence, dtype=float)))
        return ClassificationReport(
            threshold=float(threshold),
            precision=float(precision_score(y_true, y_pred, zero_division=0)),
            recall=float(recall_score(y_true, y_pred, zero_division=0)),
            f1=float(f1_score(y_true, y_pred, zero_division=0)),
            roc_auc=float(roc_auc_score(y_true, proba)),
            pr_auc=float(average_precision_score(y_true, proba)),
            brier=brier,
            brier_skill_score=1.0 - brier / brier_ref,
            tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp),
            support_pos=int(y_true.sum()), support_neg=int(len(y_true) - y_true.sum()),
            no_skill_pr_auc=prevalence,
        )
