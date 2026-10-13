"""Feature selection strategies, registered by name.

    hygiene      leakage / sparsity / near-constant / redundancy rules only
    mutual_info  hygiene -> univariate mutual-information filter
    permutation  cross-validated permutation importance only
    hybrid       hygiene -> permutation importance   (the recommended default)
"""
from churn.data.schema import DatasetSchema
from churn.features.selection.base import SELECTORS, ChainedSelector, FeatureSelector, SelectionResult
from churn.features.selection.filters import HygieneFilter, MutualInformationSelector
from churn.features.selection.permutation import PermutationImportanceSelector


@SELECTORS.register("hygiene")
def _hygiene(schema: DatasetSchema, seed: int, hygiene: dict | None = None, **_) -> FeatureSelector:
    return HygieneFilter(schema, seed, **(hygiene or {}))


@SELECTORS.register("mutual_info")
def _mutual_info(schema: DatasetSchema, seed: int, hygiene: dict | None = None,
                 mutual_info: dict | None = None, **_) -> FeatureSelector:
    return ChainedSelector([HygieneFilter(schema, seed, **(hygiene or {})),
                            MutualInformationSelector(schema, seed, **(mutual_info or {}))])


@SELECTORS.register("permutation")
def _permutation(schema: DatasetSchema, seed: int, permutation: dict | None = None, **_) -> FeatureSelector:
    return PermutationImportanceSelector(schema, seed, **(permutation or {}))


@SELECTORS.register("hybrid")
def _hybrid(schema: DatasetSchema, seed: int, hygiene: dict | None = None,
            permutation: dict | None = None, **_) -> FeatureSelector:
    return ChainedSelector([HygieneFilter(schema, seed, **(hygiene or {})),
                            PermutationImportanceSelector(schema, seed, **(permutation or {}))])


__all__ = ["SELECTORS", "ChainedSelector", "FeatureSelector", "SelectionResult", "HygieneFilter",
           "MutualInformationSelector", "PermutationImportanceSelector"]
