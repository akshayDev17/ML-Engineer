# 03 · Feature selection: what I chose, and why (lead data scientist's note)

## Decision

**A two-stage hybrid: a rule-based hygiene filter, then cross-validated permutation importance on a gradient-boosted proxy model.** It runs on the training split only, on *raw* columns, before any encoding.

```
20 candidates
  │  Stage 1 — HygieneFilter (rules from the data contract + cheap statistics)
  │     leakage by contract   → exit_survey_score              (only exists after churn)
  │     redundancy |ρ|>0.85   → total_charges  (ρ=0.90 with tenure_months; keep the higher-MI one)
  │     sparsity >50% missing, near-constant >98% one value   → (none on this data)
  ▼
18 candidates
  │  Stage 2 — PermutationImportanceSelector
  │     5-fold stratified CV on TRAIN × 5 shuffles per feature = 25 importance estimates
  │     proxy model: HistGradientBoosting (native categoricals, class_weight="balanced")
  │     score: drop in average precision (PR-AUC) on the held-out fold
  │     keep iff  mean − 1·std > 0   ("reliably positive")
  ▼
8 features: days_since_last_active, satisfaction_score, num_support_tickets, tenure_months,
            contract_type, payment_method, discount_pct, acquisition_channel
```

(Code: `src/churn/features/selection/`. Config: `feature_selection` in the YAML.)

## Why each stage exists

### Stage 1: some columns must never reach a model, however "important" they look

- **Leakage is a property of the data contract, not of the data's statistics.** `exit_survey_score` is the *most* predictive column in the table. With it, test ROC-AUC jumps to **0.974** and precision to **1.000** (ablation table below). No importance-based method can catch it, because statistically it really *is* the best feature. The only defence is the schema flag `available_at_prediction=False`, enforced *before* any scoring. This is the M4 point-in-time rule made executable.
- **Redundancy is removed before importance is measured, because permutation importance can't handle it.** If two features carry the same information, shuffling one leaves the other to compensate, so *both* look unimportant and both could be dropped. Removing one of each highly correlated pair first (|Spearman ρ| > 0.85, pairwise-complete) makes stage 2 trustworthy. Of the pair, I keep the one with higher mutual information with the target.
- Sparsity and near-constant checks cost nothing and protect against degenerate columns in future data refreshes.

### Stage 2: permutation importance is the right *scoring* method here

The question to answer is: **"Does the model, given all the other features, do measurably worse on unseen data without this feature?"** Permutation importance asks exactly that.

| property this problem needs | why it matters for churn | permutation importance |
|---|---|---|
| captures **non-linear** effects | recency is log-shaped; tenure has an early-life hazard; age is U-shaped | ✅ through the non-linear proxy |
| captures **interactions** | support tickets hurt *more* when the customer is dissatisfied; price hurts Prepaid customers more | ✅ |
| **conditional** on the other features | `avg_session_minutes` correlates with churn only *through* recency (both come from latent engagement) | ✅ it adds nothing once recency is known, so it is dropped |
| measured **out-of-sample** | in-sample importances reward memorisation | ✅ held-out folds |
| uses the **imbalance-aware** objective | accuracy is meaningless at 10% prevalence | ✅ the drop in PR-AUC |
| judges a nominal feature **as one feature** | `payment_method` is 5 one-hot columns | ✅ the raw column is permuted, so all its children move together |
| model-agnostic and cheap | the final model is a neural net | ✅ about 8 seconds for 18 features × 25 repeats |
| comes with **uncertainty** | small effects are noisy at 10% prevalence | ✅ mean ± std across folds × repeats, which gives the "reliably positive" rule |

**Why a gradient-boosted proxy rather than the MLP itself?** Permutation importance needs a model refit per fold. HistGradientBoosting trains in about a second, handles raw categoricals and NaNs natively, and has similar inductive reach (non-linear plus interactions) to the downstream MLP. Running 5 MLP trainings with early stopping per selection pass would cost 10–50× more for the same ranking. The proxy only has to *rank features*, not be the production model.

## Why not the alternatives

| method (notebook taxonomy) | why not chosen as the main stage | evidence on this data |
|---|---|---|
| **Filter: Pearson correlation** with the target | linear only, and blind to interactions (the notebook's own critique); meaningless for nominal columns | — |
| **Filter: mutual information** | handles non-linearity, but is **univariate**: no interactions, no conditioning. It *keeps* `avg_session_minutes` (correlated with the true driver, but redundant given recency) and scores `monthly_charges` at **0.000**, even though its effect is a real *interaction* with contract type | kept 12 features; test PR-AUC 0.414 vs 0.423 for the hybrid |
| **Filter: chi² / ANOVA F** | univariate and needs specific input types (chi² needs non-negative counts) | — |
| **Wrapper: RFE / step-wise** | needs O(d²) model fits (or 2^d exhaustively, as the notebook notes); the greedy path is unstable with correlated features; overfits the selection to a single train/val split | — |
| **Embedded: L1 (lasso) logistic regression** | linear in the inputs, so it cannot see the U-shapes, log-shapes, or interactions; scale-dependent; with correlated features it picks one essentially at random | — |
| **Intrinsic: tree impurity importance** | computed in-sample and biased towards high-cardinality, continuous features (more possible split points) | on this data, a random forest ranks the **noise** columns `marketing_emails_opened` (0.039) and `region` (0.033) *above* the real driver `contract_type` (0.028); puts the redundant `total_charges` 2nd and the effect-free `avg_session_minutes` 3rd |
| **SHAP** | excellent for *explaining* a model, but the mean |SHAP| ranks contribution to the *prediction*, not the out-of-sample *performance* gain, and it has no built-in noise floor. I'd use it after selection, for model explanation and per-customer reason codes for the retention team | — |
| **No selection at all** (hygiene only) | works: the MLP's weight decay copes with 18 inputs | test ROC-AUC 0.825 vs 0.822: equal within noise, but with 2.25× the inputs |

## What the selection actually bought (honest assessment)

From `notes/results/ablation.md` (test split, fixed hyper-parameters):

| variant | #features | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|
| **hybrid (chosen)** | **8** | 0.436 | 0.822 | **0.423** |
| hygiene only | 18 | 0.443 | 0.825 | 0.409 |
| hygiene → mutual information | 12 | 0.444 | 0.817 | 0.414 |
| permutation, *no* hygiene | 7 | 0.926 | 0.974 | 0.940 ← leakage, not skill |

1. **Predictive quality is unchanged.** The 8-feature model is within noise of the 18-feature model (slightly better PR-AUC, slightly worse ROC-AUC). I would not claim that selection improved accuracy here, and with 14k training rows and weight decay the MLP was never starved.
2. **The real gains are operational.** 8 instead of 18 inputs means a smaller serving contract, fewer upstream data dependencies that can break or drift (M5/M15), less monitoring surface, cheaper feature computation, and an explanation the business can follow: *recency, satisfaction, support pain, tenure, contract, payment method, discount, channel*.
3. **The hygiene stage is the part that prevents disasters.** The bottom row is the single most important result in this project.

## Known trade-offs and how to tune them

- **`stability_k = 1.0` is conservative.** It drops features with *real but weak* effects that can't be separated from noise at this sample size: `monthly_charges` (an interaction effect), `customer_tier`, `age`, `num_products`. This is a precision/recall trade-off *in the selection itself*. Lower `stability_k` (for example 0.5), or use a t-test across folds, to keep more weak signals. Raise it for a leaner model. With more data the error bars shrink and those features get through on their own.
- **Proxy mismatch.** A feature that only the MLP could exploit and the GBM could not would be dropped wrongly. This is unlikely for tabular data, and it can be checked by spot-retraining the MLP with a dropped feature added back.
- **Selection is itself a fitted step.** It saw only the training split. The validation and test scores above are therefore honest, but the selected set should be re-derived (not reused) whenever the model is retrained on new data.
