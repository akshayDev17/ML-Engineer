# 01 · The dummy dataset and the assumed pattern

**Problem.** A subscription business wants to know, at a snapshot date (`2026-09-30`), which customers will churn in the next 60 days, so the retention team can act first. Each row is one customer at the snapshot. `churn = 1` means the customer left.

## Feature dictionary

The brief asks for six columns. Fifteen more are added, covering every feature type. A few are *traps* that a good pipeline has to catch.

| column | type | role in the story |
|---|---|---|
| `customer_id` | identifier | entity key. Never a feature, and it drives de-duplication |
| `transaction_amount` | continuous | 90-day average transaction value. Log-normal (right-skewed) |
| `contract_type` | **nominal** | `Prepaid / Postpaid / Business / Family-Share`. These are contract *families*, so no category is "more" than another. That makes the column one-hot encoded, never rank encoded |
| `payment_method` | nominal | `Credit Card / Debit Card / Bank Transfer / E-Wallet / Mailed Check` |
| `last_active_date` | date | turned into `days_since_last_active`, measured from the as-of date |
| `churn` | target | binary, imbalanced |
| `tenure_months` | discrete numeric | Gamma-distributed. Drives the loyalty tier |
| `monthly_charges` | continuous | contract premium + 14 × products + noise |
| `total_charges` | continuous | ≈ tenure × monthly. **Deliberately redundant** |
| `num_support_tickets` | discrete (count) | Poisson. Its rate rises as latent satisfaction falls |
| `num_products` | discrete | 1–8 |
| `age` | discrete | weak U-shaped effect |
| `avg_session_minutes` | continuous | driven by latent engagement. **Has no direct effect on churn**: it is only *correlated* with the real driver (recency) |
| `discount_pct` | continuous | protective |
| `satisfaction_score` | **ordinal** | Very Dissatisfied < … < Very Satisfied |
| `customer_tier` | **ordinal** | Bronze < Silver < Gold < Platinum. Driven by tenure |
| `income_bracket` | ordinal | **noise** |
| `region` | nominal | **noise** |
| `acquisition_channel` | nominal | Referral customers are stickier; Telesales customers less so |
| `is_paperless_billing` | binary | very weak effect |
| `marketing_emails_opened` | discrete | **noise** |
| `exit_survey_score` | discrete | **target leakage**: it only exists *after* a customer has churned |

## The assumed pattern (advanced generator: `data.generator: pattern`)

Two unobserved latent variables, **engagement** and **satisfaction** (both ~N(0,1)), generate the behaviour:

```
engagement   ─► avg_session_minutes ↑,  days_since_last_active ↓
satisfaction ─► satisfaction_score ↑,   num_support_tickets ↓
tenure       ─► customer_tier ;  contract & products ─► monthly_charges
tenure × monthly × (1 − discount) ─► total_charges   (redundant by construction)
```

The churn log-odds are an additive model of the *observables*. Each term is a churn mechanism you would expect in reality:

| term | effect |
|---|---|
| contract | Prepaid +1.0, Postpaid 0, Family −0.5, Business −0.8 |
| payment | Mailed Check +0.7, E-Wallet +0.5, Bank Transfer −0.4 (auto-pay is sticky) |
| early-tenure hazard | `+1.2·exp(−tenure/8) − 0.01·tenure` (non-linear) |
| recency | `+0.8·(log(1+days_inactive) − log 8)` (log-shaped) |
| support pain | `+0.30·tickets·(1 + 0.6·[dissatisfied])` (**interaction**) |
| satisfaction | −0.45 per level |
| price sensitivity | `+0.015·(monthly − 60)·(1 + [Prepaid])` (**interaction**) |
| discount, products, tier, spend | protective |
| age | `+0.0006·(age − 42)²` (U-shape) |
| region, income, marketing emails | 0 (pure noise) |
| unobserved heterogeneity | N(0, 0.3) |

**How `--imbalance-ratio` is honoured without breaking the pattern.** The intercept `b0` is found by bisection so that `mean(sigmoid(b0 + score)) = 1/(1 + ratio)`. Then `churn ~ Bernoulli(p)`. The base rate moves, and every relationship stays intact. With ratio 9, the realised churn rate is ≈ 9.9%.

**Theoretical ceiling.** Scoring the clean data with the generator's *true* probabilities gives ROC-AUC ≈ 0.86 and PR-AUC ≈ 0.49 (see `notes/results/ablation.md`). Churn is stochastic, so a good model should come close to this ceiling but cannot beat it.

## The vanilla generator (`data.generator: random`)

It uses the same marginal distributions, but every column is drawn independently and the label is a coin flip at the requested rate. This is the *literal* "dummy data", and the pipeline should find **nothing** in it. It is kept as a **negative control**: on this data the vanilla run reports chance-level ROC-AUC (0.48–0.49 across runs). A pipeline that reported real skill here would be leaking.

## CLI contract

```
python -m churn --n-rows 20000 --imbalance-ratio 9
```

- `--imbalance-ratio` is **majority:minority** (the usual "imbalance ratio" definition): 9 means 9 retained customers per churner, so 10% churn.
- The defaults are 20,000 rows and ratio 9. Real telecom/SaaS monthly churn usually sits between 5% and 25%. 20k rows leaves about 300 churners in each of val and test, which is enough for stable PR-AUC estimates.
