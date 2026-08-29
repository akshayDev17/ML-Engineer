"""Schema contract for the raw transaction feed — the single source of truth enforced at every ingestion door."""

import pandera.pandas as pa
from pandera.typing import Series


class Transaction(pa.DataFrameModel):
    """Schema contract for the raw transaction feed."""

    transaction_id: Series[str] = pa.Field(unique=True)
    amount: Series[float] = pa.Field(ge=0)  # non-negative
    merchant_category: Series[str] = pa.Field(str_matches=r"^\d{4}$")
    event_ts: Series["datetime64[ns]"] = pa.Field(nullable=False)

    class Config:
        strict = True   # reject undeclared columns (schema drift is loud)
        coerce = False  # never silently cast — fail loudly instead
