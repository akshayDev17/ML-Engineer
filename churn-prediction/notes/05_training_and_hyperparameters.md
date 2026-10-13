# 05 · The network, its hyper-parameters, and the validation set

## Split

Stratified **70 / 15 / 15** → 13,855 / 2,970 / 2,970 rows, each ≈ 9.8% churn.

- **Stratified** so the rare class keeps the same rate in every split.
- **Random rather than temporal**, because each row is one customer at a *single* snapshot. There is no time order *across* rows to respect. If several monthly snapshots were stacked, the split would have to be temporal *and* grouped by `customer_id` (M10).
- **Entity-deduplicated before splitting**, so no customer can sit on both sides.

## Architecture (fixed / vanilla)

```
input (26 = 8 selected features after one-hot / rank / missing-indicators)
 → Linear(26→64) → BatchNorm1d → ReLU → Dropout(0.3)
 → Linear(64→32) → BatchNorm1d → ReLU → Dropout(0.3)
 → Linear(32→1)  = churn logit          (sigmoid only at inference)
≈ 4k parameters
```

- **A funnel MLP**, because the inputs are a few dozen dense, standardised features. Convolutions or attention would add structure the data doesn't have. Two hidden layers can represent the interactions and non-linearities in the pattern. The tuner also explores `residual_mlp` (pre-norm residual blocks) and depths of 1–3.
- **One logit + `BCEWithLogitsLoss`**: numerically stable (log-sum-exp fused), and it takes `pos_weight` directly.
- **Output bias initialised to logit(effective prior)**, so training doesn't waste early epochs learning the base rate (see `ChurnNetwork.init_output_bias`).
- **Polymorphic**: `ChurnNetwork` (ABC) → `MLPChurnNet`, `ResidualMLPChurnNet`, chosen by `model.architecture.name`.

## Hyper-parameters and the values fixed for the vanilla run

| hyper-parameter | value | why this value |
|---|---|---|
| hidden layers | `[64, 32]` | enough capacity for ~26 inputs with interactions; 4k parameters against 14k rows is a comfortable ratio |
| activation | ReLU | standard and cheap; the tuner also tries GELU/SiLU |
| batch normalisation | on | stabilises training on mixed-scale tabular inputs, and permits a higher learning rate |
| dropout | 0.3 | regularises a small MLP on noisy labels; ≥ 0.5 underfits at this size |
| optimizer | AdamW | Adam with *decoupled* weight decay, so the L2 penalty is not distorted by the adaptive learning rates |
| learning rate | 1e-3 | Adam's well-tested default for small MLPs |
| weight decay | 1e-4 | mild L2; the main regulariser alongside dropout and early stopping |
| batch size | 256 | ≈ 25 churners per batch at 10% prevalence, enough for a stable gradient on the minority class; `drop_last` avoids a size-1 BatchNorm batch |
| max epochs | 100 | an upper bound only; early stopping decides |
| early-stopping monitor | **validation PR-AUC** | threshold-free and imbalance-aware. Unlike the weighted training loss, it is unaffected by `pos_weight` |
| early-stopping patience | 10 epochs | val PR-AUC is noisy with ≈ 290 positives; shorter patience stops on noise |
| LR schedule | ReduceLROnPlateau ×0.5 after 4 flat epochs | fine-tunes once progress stalls; patience 4 < 10, so the LR drops before training is stopped |
| gradient clipping | max-norm 1.0 | protects against occasional large gradients from `pos_weight ≈ 9` |
| positive-class weight | `n_neg/n_pos ≈ 9.15` | from the imbalance strategy (`notes/04`) |
| seed | 42 | torch, numpy, and the DataLoader generator are all seeded (M7) |

## Where the validation set is used, and where it is not

| decision | made on |
|---|---|
| gradient updates (the weights) | **train** only |
| fitting imputers, outlier caps, scalers, encoders, and feature selection | **train** only |
| *when to stop* (early stopping; best weights are restored) | **validation** PR-AUC |
| *when to decay the learning rate* | **validation** PR-AUC |
| *which hyper-parameters win* (Optuna objective) | **validation** PR-AUC |
| *where to cut the probability* (decision threshold) | **validation** precision/recall curve |
| reporting precision, recall, F1, ROC-AUC, PR-AUC | **test**, touched exactly once |

Because the validation set drives four decisions, validation metrics are *optimistic*. That is precisely why a separate test set exists. For a smaller dataset I would replace the single validation split with nested cross-validation for the tuning stage.

## Reading the training curves (`evaluation/training_curves.png`)

- The **train loss is weighted** (positives count about 9×), and the **validation loss is not** (it is measured at the real prior). They are on different scales by construction, so "val loss < train loss" here is not a bug. The panel exists to show each curve's *trend*.
- Validation PR-AUC rises fast for about 5 epochs and plateaus around 0.43. The best epoch (25 in the final run) is the checkpoint that gets restored, and early stopping ended training at epoch 35.
