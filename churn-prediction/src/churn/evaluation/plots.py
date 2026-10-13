"""Static evaluation figures (PNG). Colors follow a validated categorical order: the model
is series slot 1 (blue), a second series slot 2 (orange); reference lines are recessive gray.
Two measures with different scales are drawn as two panels, never on a dual axis."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

from churn.modeling.callbacks import EpochLog  # noqa: E402

SURFACE, INK, INK_MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES_1, SERIES_2, REFERENCE = "#2a78d6", "#eb6834", "#9a9890"


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=12, loc="left")
    ax.set_xlabel(xlabel, color=INK_MUTED)
    ax.set_ylabel(ylabel, color=INK_MUTED)
    ax.tick_params(colors=INK_MUTED)
    ax.grid(color=GRID, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_visible(False)


def _figure(ncols: int = 1):
    fig, axes = plt.subplots(1, ncols, figsize=(5.6 * ncols, 4.6), facecolor=SURFACE)
    return fig, np.atleast_1d(axes)


class EvaluationPlotter:
    def __init__(self, out_dir: str | Path) -> None:
        self._out = Path(out_dir)
        self._out.mkdir(parents=True, exist_ok=True)

    def roc_curve(self, y_true, proba, auc: float, threshold: float) -> Path:
        fpr, tpr, thr = roc_curve(y_true, proba)
        fig, (ax,) = _figure()
        ax.plot([0, 1], [0, 1], color=REFERENCE, linestyle="--", linewidth=1.5, label="no-skill (AUC 0.5)")
        ax.plot(fpr, tpr, color=SERIES_1, linewidth=2, label=f"MLP (AUC {auc:.3f})")
        i = int(np.argmin(np.abs(thr - threshold)))
        ax.scatter([fpr[i]], [tpr[i]], s=64, color=SERIES_1, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(f"operating point t={threshold:.2f}", (fpr[i], tpr[i]), xytext=(12, -16),
                    textcoords="offset points", color=INK)
        _style(ax, "ROC curve — test set", "False positive rate", "True positive rate (recall)")
        ax.legend(frameon=False, loc="lower right", labelcolor=INK)
        return self._save(fig, "roc_curve.png")

    def pr_curve(self, y_true, proba, ap: float, threshold: float) -> Path:
        precision, recall, thr = precision_recall_curve(y_true, proba)
        prevalence = float(np.mean(y_true))
        fig, (ax,) = _figure()
        ax.axhline(prevalence, color=REFERENCE, linestyle="--", linewidth=1.5,
                   label=f"no-skill (precision = prevalence {prevalence:.2f})")
        ax.plot(recall, precision, color=SERIES_1, linewidth=2, label=f"MLP (PR-AUC {ap:.3f})")
        i = int(np.argmin(np.abs(thr - threshold)))
        ax.scatter([recall[i]], [precision[i]], s=64, color=SERIES_1, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(f"t={threshold:.2f}", (recall[i], precision[i]), xytext=(10, 8), textcoords="offset points",
                    color=INK)
        _style(ax, "Precision–recall curve — test set", "Recall", "Precision")
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, loc="upper right", labelcolor=INK)
        return self._save(fig, "pr_curve.png")

    def training_curves(self, history: list[EpochLog], best_epoch: int) -> Path:
        epochs = [e.epoch for e in history]
        fig, (ax_loss, ax_auc) = _figure(2)
        ax_loss.plot(epochs, [e.train_loss for e in history], color=SERIES_1, linewidth=2, label="train (weighted)")
        ax_loss.plot(epochs, [e.val_loss for e in history], color=SERIES_2, linewidth=2, label="validation")
        _style(ax_loss, "Loss (BCE)", "Epoch", "Loss")
        ax_loss.legend(frameon=False, labelcolor=INK)
        ax_auc.plot(epochs, [e.val_pr_auc for e in history], color=SERIES_1, linewidth=2, label="val PR-AUC")
        _style(ax_auc, "Validation PR-AUC (early-stopping monitor)", "Epoch", "PR-AUC")
        for ax in (ax_loss, ax_auc):
            ax.axvline(best_epoch, color=REFERENCE, linestyle=":", linewidth=1.5)
        ax_auc.annotate(f"best epoch {best_epoch}", (best_epoch, ax_auc.get_ylim()[0]), xytext=(6, 8),
                        textcoords="offset points", color=INK_MUTED)
        return self._save(fig, "training_curves.png")

    def _save(self, fig, name: str) -> Path:
        path = self._out / name
        fig.tight_layout()
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(fig)
        return path
