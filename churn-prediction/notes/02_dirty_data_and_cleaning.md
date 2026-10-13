# 02 · Dirty data, and how each kind of dirt is removed

The clean synthetic table is deliberately dirtied by `DirtyDataInjector`, written to `data/churn_raw.csv`, and read back **as text** (schema-on-read). The pipeline therefore starts the way a real CRM/billing extract does: untyped strings.

## Dirt → remedy map

| dirt injected (`data/corruption.py`) | example | remedy | where | fitted? |
|---|---|---|---|---|
| null tokens | `""`, `"N/A"`, `"?"`, `"-"`, `"none"` | → `NaN` | `NormalizeNullTokens` | no |
| category spelling noise | `" PREPAID"`, `"pre-paid"`, `"cc"`, `"ewallet"` | canonical value via schema aliases; unknown → `NaN` | `CanonicalizeCategories` | no |
| numbers as formatted text | `"$1,234.50"`, `"USD 81.1"`, `"12 months"` | strip symbols → float | `ParseNumeric` | no |
| mixed date formats | `05-Sep-2026`, `2026/09/05`, `Sep 05, 2026`, `20260905` | try each known format | `ParseDates` | no |
| unparseable / future dates | `0000-00-00`, a date after the snapshot | → `NaT` | `ParseDates` | no |
| **invalid** values | age 999 / −1, tenure −3, discount 150%, negative spend | outside the schema domain → `NaN` | `EnforceValidRanges` | no |
| **extreme but valid** values | a spend 40× the median (a whale) | winsorised at Tukey's outer fence `Q3 + 3·IQR` | `IQRCapper` | **yes (train)** |
| duplicate records | the same customer re-ingested, id as `" cust-000123 "` | normalise id → keep first | `NormalizeIdentifier`, `DropDuplicateEntities` | no |
| label chaos | `Yes/yes/1/TRUE/churned/Y`, `No/0/stayed/N`, missing | → {0, 1}; unlabelled rows dropped | `ParseTarget` | no |
| missing values (all of the above) | — | median / most-frequent / explicit `"Missing"` category + missing-indicator columns | `TabularPreprocessor` stage 1 | **yes (train)** |
| skew | log-normal spend, exponential recency | `log1p` on columns with train skewness > 1 | `SkewCorrector` | **yes (train)** |
| scale differences | tenure in months, charges in currency | `StandardScaler` (numeric), `MinMaxScaler` (ordinal ranks) | stage 2 | **yes (train)** |

## The rule that keeps cleaning leakage-free

> A step that only needs **the schema and the row** may run on the whole dataset before the split. A step that needs **statistics of the data** (a median, a quartile, a mean/std, a category list) is a *fitted transformer*, fitted on the **training split only**.

That is why cleaning is split into two families:

1. **`DataCleaner` (stateless, before the split).** It parses, canonicalises, invalidates, and de-duplicates. It is **idempotent**: cleaning cleaned data changes nothing, and a test asserts this. The *same class* is reused by the serving predictor (`DataCleaner.for_inference`), so production requests go through exactly the same parsing rules.
2. **`TabularPreprocessor` (fitted on train, after the split).** It imputes, caps, transforms skew, scales, and encodes. The fitted object is saved in the model bundle.

### Why de-duplicate *before* the split

If a customer appears twice and the copies land in train and test, the model is graded on a row it has already memorised. Entity de-duplication is therefore a pre-split, stateless step (M10: grouped leakage).

### Invalid ≠ outlier

- **Age 999** is impossible. It is a data-entry error, so it becomes `NaN` and is then imputed. Capping it would invent a 90-something-year-old customer.
- **A 40× spender** is unusual but real, and informative. Deleting the row throws away a customer. Capping keeps the row while stopping one value from dominating the scaler's mean/std and the gradients.
- The fence is fitted on train: `k = 3.0` caps only "extreme" outliers (Tukey's outer fence), which is the more conservative choice for a feature that carries signal.

### Missingness as a feature

Who skips the CSAT survey? Disengaged customers, who also churn more. Imputation erases that information, so stage 1 adds a `missing_<col>` indicator for numeric, ordinal, and binary columns. Nominal columns don't need one: their `"Missing"` category becomes its own one-hot column.

### Encoding by type (from the schema, never guessed)

| type | encoding | why |
|---|---|---|
| nominal (`contract_type`, `payment_method`, …) | one-hot, `handle_unknown="ignore"` | no order exists; an unseen category at serving time becomes all-zeros instead of crashing |
| ordinal (`satisfaction_score`, `customer_tier`, …) | rank in schema order → min-max to [0, 1] | keeps the order with a single column; the order comes from the contract, not from `LabelEncoder`'s alphabetical order |
| binary | 0/1 passthrough | — |
| numeric | (log1p if skewed) → standardise | an MLP trains best on zero-mean, unit-variance inputs |
