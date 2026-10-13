# 09 · Design: SOLID, patterns, and OOP in this codebase

## Package map

```
src/churn/
├── cli.py              entry point: --n-rows, --imbalance-ratio (nothing else)
├── config.py           frozen, typed config dataclasses (YAML → dataclass, unknown keys rejected)
├── factory.py          COMPOSITION ROOT: the only place config strings become classes
├── pipeline.py         orchestration: data → split → select → prepare → tune → train → evaluate → package
├── common/             Registry, seeding, logging
├── data/               schema (the contract) · generators/ · corruption · cleaning · splitting · repository
├── features/           engineering · transformers · preprocessing · selection/
├── imbalance/          balancing strategies
├── modeling/           networks · trainer · callbacks · service (facade)
├── tuning/             fixed · optuna
├── evaluation/         metrics · thresholds · plots
└── serving/            exporters · bundle (+ local registry) · predictor (+ backends) · app (FastAPI)
```

## SOLID

| principle | where it shows |
|---|---|
| **S**ingle responsibility | Each `Corruption`, each `CleaningStep`, and each selector stage does one thing. The `Trainer` trains; it does not decide when to stop (that is `EarlyStopping`) or how to log (`ProgressLogger`). |
| **O**pen/closed | Every swappable family has a `Registry`. A new imbalance strategy, network, selector, tuner, threshold policy, exporter, or inference backend is a new class with a `@REGISTRY.register("name")` decorator, plus a YAML edit. No existing code changes. |
| **L**iskov substitution | `MLPChurnNet` and `ResidualMLPChurnNet` are interchangeable everywhere a `ChurnNetwork` is expected: trainer, tuner, ONNX exporter, predictor. Every `FeatureSelector` returns a `SelectionResult`, and every `ImbalanceStrategy` returns a `BalancedTrainingSet`. |
| **I**nterface segregation | `Callback` hooks are no-op by default, so each observer overrides only the events it needs. `ThresholdPolicy`, `ModelExporter`, and `InferenceBackend` are one-method interfaces. |
| **D**ependency inversion | `ChurnPipeline` depends only on abstractions in `PipelineComponents`. `factory.build_components` injects the concrete ones. Tests build pipelines into temporary directories by injecting different paths and configs. |

## Design patterns

| pattern | class(es) |
|---|---|
| **Strategy** | generators, corruptions, cleaning steps, selectors, imbalance strategies, tuners, threshold policies, scalers, exporters, inference backends |
| **Template Method** | `ChurnDataGenerator.generate()` fixes the skeleton; subclasses fill in `_sample_features` and `_churn_probability`. `ChurnNetwork` fixes `forward`, `predict_proba`, and bias initialisation; subclasses fill in `_build_body`. |
| **Factory + Registry** | `common/registry.py` and `factory.py` |
| **Composite** | `DirtyDataInjector` (list of `Corruption`s), `DataCleaner` (chain of `CleaningStep`s), `ChainedSelector` (hygiene → permutation) |
| **Observer** | `Trainer` publishes epoch events to `EarlyStopping`, `ReduceLROnPlateauCallback`, `ProgressLogger`, and `OptunaPruningCallback` |
| **Builder** | `TabularPreprocessor` assembles the two `ColumnTransformer` stages from the schema |
| **Facade** | `ModelTrainingService` (spec → trained network), `ChurnPredictor` (raw dict → decision) |
| **Adapter** | `_RenamingColumnTransformer` (normalises sklearn output names), `OptunaPruningCallback` (our observer protocol → Optuna's pruning protocol) |
| **Repository** | `CsvDatasetRepository`, `LocalModelRegistry` |
| **Value object** | frozen dataclasses: `RunArgs`, all `*Config`, `ModelSpec`, `Split`, `ClassificationReport` |

## OOP pillars

- **Abstraction.** ABCs define *what* a component does: `ChurnDataGenerator`, `Corruption`, `CleaningStep`, `FeatureSelector`, `ImbalanceStrategy`, `ChurnNetwork`, `HyperparameterTuner`, `ThresholdPolicy`, `ModelExporter`, `InferenceBackend`, `DataSplitter`.
- **Inheritance.** Concrete classes extend these. `ChurnNetwork` itself inherits from `nn.Module` *and* `ABC`.
- **Polymorphism.** The pipeline calls `selector.select(...)`, `imbalance.prepare(...)`, `tuner.tune(...)`, and `backend.logits(...)` without knowing which implementation it holds. Vanilla vs advanced is decided purely by which object was injected.
- **Encapsulation.** Fitted state is private (`TabularPreprocessor._sanitizer`, `_encoder`) and reached only through methods that check it is fitted. Configs and specs are frozen. The schema exposes queries, not its internal dict. The model registry is append-only, so a version cannot be overwritten (`mkdir(exist_ok=False)`).

## Vanilla ↔ advanced swap points

| requirement | vanilla | advanced | config key |
|---|---|---|---|
| dummy data | `random` | `pattern` | `data.generator` |
| imbalance handling | `none` | `class_weight` · `smotenc` · `weighted_sampler` · `random_undersample` | `imbalance.strategy` |
| hyper-parameters | `fixed` | `optuna` | `tuning.strategy` |
| decision threshold | `fixed` (0.5) | `max_fbeta` · `min_recall` | `threshold.policy` |

`configs/vanilla.yaml` and `configs/advanced.yaml` are the two pure profiles. Any single line can be flipped on its own, because the components share interfaces.
