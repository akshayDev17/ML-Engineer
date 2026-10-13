# 04 · Class imbalance: creating it, and "balancifying" it

## Creating it

`--imbalance-ratio R` (majority:minority, default 9) sets the target positive rate `1/(1+R)`. The pattern generator solves for the logit intercept that produces this rate while keeping every feature effect intact (`notes/01`). Stratified splitting then keeps the rate at ≈ 9.8% in train, val, and test.

## The non-negotiable rules

1. **Rebalance the training split only.** Validation and test must keep the real-world prior. Otherwise precision, PR-AUC, and the chosen threshold describe a world that doesn't exist.
2. **Rebalance after the split, and after imputation, but before one-hot encoding.** SMOTE-NC needs the real category values. Interpolating one-hot columns produces impossible "half-Prepaid" customers. The two-stage preprocessor exists to provide exactly this seam (`features/preprocessing.py`).
3. **Fit scalers and encoders on real rows only.** In the pipeline, the encoder is fitted *before* any synthetic rows exist.
4. **Choose the threshold afterwards, on validation.** Every rebalancing method shifts the predicted probabilities, so the 0.5 cut-off loses whatever meaning it had.

## Strategies implemented (`imbalance.strategy`)

| strategy | mechanism | pros | cons |
|---|---|---|---|
| `none` (**vanilla**) | natural prior, plain BCE | probabilities stay calibrated to the real base rate | the default 0.5 threshold predicts almost no churners |
| `class_weight` (**advanced default**) | `BCEWithLogitsLoss(pos_weight=(n_neg/n_pos)^power)` | no rows invented or discarded; one knob; zero cost | inflates the probabilities (they are no longer calibrated) |
| `weighted_sampler` | `WeightedRandomSampler`, so each mini-batch is ~50/50 | balanced gradients in every step | repeats minority rows within an epoch; noisier epochs |
| `smotenc` | synthetic minority rows by neighbour interpolation (categoricals by neighbour majority) | adds variety rather than copies | can create unrealistic points in overlapping regions; costs more; the notebook warns its distributional assumption is weaker in low dimensions |
| `random_undersample` | drop majority rows | fast; honest | throws away about 70% of the majority's information (fine only when data is plentiful) |

## What actually happened (test split, `notes/results/ablation.md`)

| strategy | precision | recall | F1 | ROC-AUC | PR-AUC | val-chosen threshold |
|---|---:|---:|---:|---:|---:|---:|
| none | 0.401 | 0.500 | 0.445 | 0.821 | 0.423 | 0.214 |
| class_weight (power 1.0) | 0.424 | 0.449 | 0.436 | 0.822 | 0.423 | 0.747 |
| class_weight (power 0.5) | 0.413 | 0.497 | 0.451 | 0.822 | 0.424 | 0.467 |
| weighted_sampler | 0.395 | 0.524 | 0.451 | 0.819 | 0.421 | 0.690 |
| smotenc | 0.368 | 0.483 | 0.418 | 0.808 | 0.401 | 0.524 |
| random_undersample | 0.413 | 0.507 | 0.455 | 0.822 | 0.426 | 0.557 |

**The lesson, stated plainly:** with a flexible model, a reasonable amount of data (≈ 1,400 training churners), and a threshold tuned on validation, **every strategy lands within about ±0.02 F1, with near-identical ranking quality (ROC/PR-AUC)**. Rebalancing mostly *moves where the threshold has to sit* (0.21 unweighted vs 0.75 fully weighted), not how well the model ranks customers. SMOTE-NC is slightly *worse* here, because interpolated customers in the overlap region blur the decision boundary.

The 0.5-threshold comparison shows where imbalance handling really hurts when ignored:

- `none` @ 0.5 on the vanilla run: **0 churners flagged** (recall 0.0, "accuracy" 90%).
- `class_weight` @ 0.5: recall 0.777 but precision 0.249. After moving the threshold to the F1 optimum: precision 0.424 and recall 0.449.

## Why `class_weight` is still the advanced default

- It matches the best options on ranking quality, invents no data, and discards nothing.
- It makes the *training signal* balanced. That should matter more as imbalance becomes extreme (1:100+), where the minority's share of the gradient shrinks towards nothing. At ratio 9 it made no measurable difference, so treat this as the expected direction rather than a measured result. To probe it, run `python -m churn --n-rows 100000 --imbalance-ratio 99` with each strategy (more rows keep val/test churners countable).
- It is one line in the loss and has no extra training cost. SMOTE-NC needs a neighbour search over the whole training set.

**If calibrated probabilities are needed** (for example, expected-value retention budgeting: *offer if p·CLV > cost*), use `none`, or undo the prior shift analytically: `odds_true = odds_model / pos_weight`. Alternatively, fit Platt or isotonic calibration on the validation split.
