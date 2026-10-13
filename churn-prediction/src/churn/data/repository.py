"""Persistence boundary for datasets (Repository pattern): the rest of the code never
touches file paths or CSV dialects directly."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


class CsvDatasetRepository:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self._root / f"{name}.csv"

    def save(self, df: pd.DataFrame, name: str) -> Path:
        path = self.path(name)
        df.to_csv(path, index=False)
        return path

    def load_raw(self, name: str) -> pd.DataFrame:
        """Schema-on-read: every cell comes back as *text*; parsing is the cleaner's job."""
        return pd.read_csv(self.path(name), dtype=object, keep_default_na=False)

    def load(self, name: str) -> pd.DataFrame:
        return pd.read_csv(self.path(name))
