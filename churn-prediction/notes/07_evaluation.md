# 07 · Test-set evaluation

All numbers come from the default run (`python -m churn`: advanced profile, 20,000 rows, ratio 9), on the **test split: 2,970 customers, 292 churners (9.8%)**. The threshold was chosen on validation, and the test set was scored once.

## Headline

| metric | value | how to read it |
|---|---:|---|
| **Precision** | **0.412** | of the customers we flag, 41% really churn (vs 9.8% if we flagged at random): a **4.2× lift** |
| **Recall** | **0.459** | we catch 46% of the customers who will churn |
| **F1** | **0.434** | harmonic mean at the F1-optimal (validation-chosen) threshold of 0.705 |
| **ROC-AUC** | **0.819** | P(a random churner is scored above a random stayer) = 0.82 |
| PR-AUC (average precision) | 0.424 | vs a no-skill baseline of 0.098 (= prevalence) |
| Brier score | 0.156 | probabilities are inflated by `pos_weight`, so this is *not* a calibration claim (`notes/04`) |

Confusion matrix at t = 0.705:

|  | predicted stay | predicted churn |
|---|---:|---:|
| **actual stay** | TN 2,487 | FP 191 |
| **actual churn** | FN 158 | TP 134 |

**Context:** the generator's *true* probabilities reach ROC-AUC 0.859 and PR-AUC 0.489 (the oracle ceiling). The model recovers most of the learnable signal, even though it was trained on dirtied, imputed data.

## Figures (in each bundle's `evaluation/` folder)

- `roc_curve.png`: the ROC curve against the no-skill diagonal, with the operating point marked.
- `pr_curve.png`: the precision–recall curve against the prevalence line. **This is the more honest plot for 10% prevalence**: ROC stays flattering because false positives are diluted by the large negative class (M10).
- `training_curves.png`: loss and validation PR-AUC per epoch, with the restored best epoch marked.

## Why the threshold matters more than anything else here

The same model and the same scores give very different precision/recall at different cut-offs:

| threshold policy (chosen on validation) | t | precision | recall | F1 |
|---|---:|---:|---:|---:|
| fixed 0.5 | 0.500 | 0.264 | 0.733 | 0.388 |
| **max F1** (default) | 0.705 | **0.412** | **0.459** | **0.434** |
| max F2 (a missed churner costs ~2× a wasted offer) | ≈0.54 | ≈0.27 | ≈0.74 | — |
| recall ≥ 0.8 (retention must reach 80% of churners) | ≈0.49 | ≈0.24 | ≈0.78 | — |

(The last two rows come from the fixed-hyper-parameter ablation in `notes/results/ablation.md`.)

The *right* row is a business decision: the cost of a retention offer versus the customer lifetime value lost per missed churner, and the retention team's capacity. The pipeline makes the decision explicit and configurable (`threshold.policy`), stores the chosen value in the model bundle, and reports test metrics at both the chosen threshold and 0.5.

## Metric hygiene applied

- ROC-AUC and PR-AUC are computed from **probabilities**, never from hard labels.
- Every metric call uses `(y_true, y_pred)` order.
- `zero_division=0` guards precision when nothing is flagged (the vanilla 0.5 case).
- Accuracy is not reported as a headline: predicting "no churn" for everyone already scores ≈ 90%.
