# 10 · What was reused from the notebooks, and what was corrected

The brief says to use "topics that you deem factually correct" from `Machine-Learning-Concepts/src`. Most of the content there carried over directly. A few code patterns are wrong or outdated, and this project deliberately does them differently.

## Carried over

| notebook | idea | used in |
|---|---|---|
| `FeatureSelection.ipynb` | intrinsic / filter / wrapper taxonomy; univariate filters miss non-linear and interaction signal; permutation importance | `features/selection/`, `notes/03` |
| `feature-engineering.ipynb` | nominal → one-hot, ordinal → rank encoding with an explicit order; missingness as information | `features/preprocessing.py` |
| `handling-outliers.ipynb` | IQR fences (1.5× inner, 3× extreme), capping instead of deleting | `features/transformers.IQRCapper` |
| `imbalanced-classification/` | accuracy is misleading; PR curves for skewed data; Brier skill score; SMOTE, under-sampling, SMOTE-Tomek | `imbalance/`, `evaluation/metrics.py` |
| `auc_roc/`, `confusion_matrix/` | ROC from scores; confusion-matrix layout | `evaluation/` |
| `pytorchPimadiabetes.ipynb` | `nn.Module` subclass, Adam, a training loop | `modeling/` |

## Corrected

| notebook pattern | problem | what this project does |
|---|---|---|
| `roc_auc_score(y_test, y_pred)` with **hard** predictions (`imbalanced-classification/main.ipynb`) | AUC is a ranking metric. With 0/1 predictions it collapses to the balanced accuracy at a single threshold. | AUC from probabilities: `roc_auc_score(y, proba)` |
| `classification_report(y_predArr, y_test)` and `accuracy_score(y_pred, y_test)` (Pima, imbalance notebooks) | Arguments are swapped. sklearn's signature is `(y_true, y_pred)`, so precision and recall are reported *transposed*. | Always `(y_true, y_pred)` |
| `df_train.loc[df_train['Age'] > uE] = uE` (`handling-outliers.ipynb`) | Assigns the cap to **every column of those rows**, not only `Age`. | Column-wise `np.clip` with fences learned on train |
| Outlier fences / scalers computed on the full dataset before `train_test_split` | Test-set statistics leak into training. | All fitted statistics come from the training split only |
| Resampling with `fit_sample(...)` (`imblearn`) | Removed in imbalanced-learn ≥ 0.8. | `fit_resample` |
| Plain SMOTE on data that would contain categorical columns | SMOTE interpolates and invents impossible half-categories. | SMOTE-NC for mixed-type data, run *before* one-hot encoding |
| `KFold(n_splits=5, shuffle=False, random_state=42)` | Recent sklearn raises an error; `random_state` only matters with `shuffle=True`. On an imbalanced target it should also be stratified. | `StratifiedKFold(5, shuffle=True, random_state=seed)` |
| No validation set; 500 full-batch epochs on train; the test set used to judge every choice (Pima) | Every decision tuned on test makes the test estimate optimistic. | train / val / test; val drives early stopping, LR schedule, Optuna, and the threshold; test is touched once |
| `torch.save(model, 'diabetes.pt')` (pickles the whole module) | Fragile: it ties the file to the exact class and module path. Loading needs unpickling of arbitrary code. | `state_dict` + architecture in metadata, loaded with `weights_only=True`; ONNX for serving |
| Two-logit output + `CrossEntropyLoss` for a binary target | Not wrong, but it doubles the head and has no direct `pos_weight`. | One logit + `BCEWithLogitsLoss(pos_weight=…)` |
| Accuracy reported as the headline metric for imbalanced data | A model that predicts "no churn" for everyone scores ≈ 90%. | Precision, recall, F1, ROC-AUC, PR-AUC (with the no-skill baseline), and Brier |

The first two rows matter most. Both notebook patterns run without errors and print plausible-looking numbers, which is exactly why they are easy to miss.
