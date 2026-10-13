"""Importing this package registers every generator with `GENERATORS`."""
from churn.data.generators.base import GENERATORS, ChurnDataGenerator
from churn.data.generators.pattern_generator import PatternChurnDataGenerator
from churn.data.generators.random_generator import RandomChurnDataGenerator

__all__ = ["GENERATORS", "ChurnDataGenerator", "PatternChurnDataGenerator", "RandomChurnDataGenerator"]
