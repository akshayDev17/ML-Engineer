"""The data contract (M5): one declarative description of every column.

Every downstream component — the generators, the dirt injector, the cleaner, the feature
selector, the preprocessor and the serving predictor — reads column semantics from here
instead of hard-coding them. That is what keeps training and serving consistent (M6), and
it is what lets the hygiene filter drop a leaky column *by contract* rather than by luck.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FeatureType(str, Enum):
    IDENTIFIER = "identifier"
    CONTINUOUS = "continuous"  # real-valued, e.g. charges
    DISCRETE = "discrete"  # integer counts / durations
    NOMINAL = "nominal"  # unordered categories -> one-hot
    ORDINAL = "ordinal"  # ordered categories  -> rank encoding
    BINARY = "binary"  # yes/no flags        -> 0/1
    DATE = "date"  # timestamps -> engineered into numeric recency
    TARGET = "target"

    @property
    def is_numeric(self) -> bool:
        return self in (FeatureType.CONTINUOUS, FeatureType.DISCRETE)

    @property
    def is_categorical(self) -> bool:
        return self in (FeatureType.NOMINAL, FeatureType.ORDINAL, FeatureType.BINARY)


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    ftype: FeatureType
    description: str
    # NOMINAL: the allowed values. ORDINAL: the allowed values *in rank order* (low -> high).
    categories: tuple[str, ...] = ()
    # Physically/business-valid domain. Values outside are *invalid* (-> NaN), which is a
    # different thing from *extreme-but-valid* values (outliers, handled by a fitted capper).
    valid_min: float | None = None
    valid_max: float | None = None
    # False == the value is only known *after* the label is decided (target leakage, M4).
    available_at_prediction: bool = True
    # Free-text aliases seen in the wild, mapped onto canonical categories by the cleaner.
    aliases: dict[str, str] = field(default_factory=dict)

    @property
    def is_model_candidate(self) -> bool:
        return self.ftype not in (FeatureType.IDENTIFIER, FeatureType.DATE, FeatureType.TARGET)


class DatasetSchema:
    """An immutable, queryable collection of `FeatureSpec`s."""

    def __init__(self, specs: list[FeatureSpec], id_column: str, target: str) -> None:
        names = [s.name for s in specs]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate column names in schema")
        self._specs = {s.name: s for s in specs}
        self._id_column = id_column
        self._target = target

    @property
    def id_column(self) -> str:
        return self._id_column

    @property
    def target(self) -> str:
        return self._target

    @property
    def columns(self) -> list[str]:
        return list(self._specs)

    def __getitem__(self, name: str) -> FeatureSpec:
        return self._specs[name]

    def __contains__(self, name: str) -> bool:
        return name in self._specs

    def specs(self) -> list[FeatureSpec]:
        return list(self._specs.values())

    def of_type(self, *ftypes: FeatureType) -> list[str]:
        return [s.name for s in self._specs.values() if s.ftype in ftypes]

    def model_candidates(self) -> list[str]:
        return [s.name for s in self._specs.values() if s.is_model_candidate]

    def numeric(self, among: list[str] | None = None) -> list[str]:
        return self._filter(among, lambda s: s.ftype.is_numeric)

    def nominal(self, among: list[str] | None = None) -> list[str]:
        return self._filter(among, lambda s: s.ftype is FeatureType.NOMINAL)

    def ordinal(self, among: list[str] | None = None) -> list[str]:
        return self._filter(among, lambda s: s.ftype is FeatureType.ORDINAL)

    def binary(self, among: list[str] | None = None) -> list[str]:
        return self._filter(among, lambda s: s.ftype is FeatureType.BINARY)

    def extended(self, extra: list[FeatureSpec]) -> "DatasetSchema":
        """A new schema with engineered columns appended (the original stays untouched)."""
        return DatasetSchema(self.specs() + extra, self._id_column, self._target)

    def _filter(self, among, predicate) -> list[str]:
        pool = self._specs.values() if among is None else (self._specs[n] for n in among)
        return [s.name for s in pool if predicate(s)]


_YES_NO_ALIASES = {"y": "Yes", "yes": "Yes", "true": "Yes", "1": "Yes", "n": "No", "no": "No", "false": "No", "0": "No"}

RAW_SPECS: list[FeatureSpec] = [
    # --- the six columns from the problem statement --------------------------------------
    FeatureSpec("customer_id", FeatureType.IDENTIFIER, "Unique customer key (never a feature)."),
    FeatureSpec(
        "transaction_amount", FeatureType.CONTINUOUS,
        "Average transaction value over the last 90 days (currency). Right-skewed.",
        valid_min=0.0,
    ),
    FeatureSpec(
        "contract_type", FeatureType.NOMINAL,
        "Commercial contract family. Deliberately NOMINAL: no category is 'more' than another.",
        categories=("Prepaid", "Postpaid", "Business", "Family-Share"),
        aliases={"pre-paid": "Prepaid", "pre paid": "Prepaid", "post-paid": "Postpaid", "post paid": "Postpaid",
                 "biz": "Business", "corporate": "Business", "family": "Family-Share", "family share": "Family-Share",
                 "familyshare": "Family-Share"},
    ),
    FeatureSpec(
        "payment_method", FeatureType.NOMINAL, "How the customer pays.",
        categories=("Credit Card", "Debit Card", "Bank Transfer", "E-Wallet", "Mailed Check"),
        aliases={"cc": "Credit Card", "creditcard": "Credit Card", "credit": "Credit Card", "debit": "Debit Card",
                 "dc": "Debit Card", "bank": "Bank Transfer", "ach": "Bank Transfer", "wire": "Bank Transfer",
                 "ewallet": "E-Wallet", "e wallet": "E-Wallet", "wallet": "E-Wallet", "check": "Mailed Check",
                 "cheque": "Mailed Check", "mailed cheque": "Mailed Check"},
    ),
    FeatureSpec("last_active_date", FeatureType.DATE, "Last day with any product activity."),
    # --- engineered-domain extras: a mix of every feature type ----------------------------
    FeatureSpec("tenure_months", FeatureType.DISCRETE, "Months since sign-up.", valid_min=0, valid_max=240),
    FeatureSpec("monthly_charges", FeatureType.CONTINUOUS, "Current monthly bill.", valid_min=0, valid_max=2_000),
    FeatureSpec(
        "total_charges", FeatureType.CONTINUOUS,
        "Lifetime billed amount. ~tenure x monthly_charges: a deliberately REDUNDANT feature.",
        valid_min=0,
    ),
    FeatureSpec("num_support_tickets", FeatureType.DISCRETE, "Support tickets in the last 90 days.", valid_min=0, valid_max=100),
    FeatureSpec("num_products", FeatureType.DISCRETE, "Number of subscribed products.", valid_min=1, valid_max=10),
    FeatureSpec("age", FeatureType.DISCRETE, "Customer age in years.", valid_min=18, valid_max=100),
    FeatureSpec("avg_session_minutes", FeatureType.CONTINUOUS, "Mean daily session length.", valid_min=0, valid_max=1_440),
    FeatureSpec("discount_pct", FeatureType.CONTINUOUS, "Current discount on the bill (%).", valid_min=0, valid_max=100),
    FeatureSpec(
        "satisfaction_score", FeatureType.ORDINAL, "Latest CSAT survey answer.",
        categories=("Very Dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very Satisfied"),
        aliases={"1": "Very Dissatisfied", "2": "Dissatisfied", "3": "Neutral", "4": "Satisfied", "5": "Very Satisfied",
                 "very unsatisfied": "Very Dissatisfied", "unsatisfied": "Dissatisfied", "ok": "Neutral",
                 "happy": "Satisfied", "very happy": "Very Satisfied"},
    ),
    FeatureSpec(
        "customer_tier", FeatureType.ORDINAL, "Loyalty tier.",
        categories=("Bronze", "Silver", "Gold", "Platinum"),
        aliases={"bronz": "Bronze", "silvr": "Silver", "gld": "Gold", "plat": "Platinum"},
    ),
    FeatureSpec(
        "income_bracket", FeatureType.ORDINAL, "Self-reported income band (weak/no signal by design).",
        categories=("Low", "Lower-Middle", "Upper-Middle", "High"),
        aliases={"lower middle": "Lower-Middle", "upper middle": "Upper-Middle", "lowermiddle": "Lower-Middle",
                 "uppermiddle": "Upper-Middle"},
    ),
    FeatureSpec(
        "region", FeatureType.NOMINAL, "Sales region (pure NOISE by design).",
        categories=("North", "South", "East", "West", "Central"),
        aliases={"n": "North", "s": "South", "e": "East", "w": "West", "c": "Central"},
    ),
    FeatureSpec(
        "acquisition_channel", FeatureType.NOMINAL, "Channel the customer was acquired through.",
        categories=("Online", "Retail Store", "Referral", "Telesales"),
        aliases={"web": "Online", "store": "Retail Store", "retail": "Retail Store", "friend": "Referral",
                 "phone": "Telesales", "tele sales": "Telesales"},
    ),
    FeatureSpec(
        "is_paperless_billing", FeatureType.BINARY, "Paperless billing enabled.",
        categories=("No", "Yes"), aliases=_YES_NO_ALIASES,
    ),
    FeatureSpec(
        "marketing_emails_opened", FeatureType.DISCRETE, "Marketing emails opened last month (pure NOISE).",
        valid_min=0, valid_max=500,
    ),
    FeatureSpec(
        "exit_survey_score", FeatureType.DISCRETE,
        "Score from the exit survey. Only exists AFTER a customer churned: TARGET LEAKAGE.",
        valid_min=1, valid_max=5, available_at_prediction=False,
    ),
    FeatureSpec("churn", FeatureType.TARGET, "1 = churned within 60 days after the snapshot."),
]

RAW_SCHEMA = DatasetSchema(RAW_SPECS, id_column="customer_id", target="churn")

# Columns created by `churn.features.engineering` from raw ones.
ENGINEERED_SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "days_since_last_active", FeatureType.DISCRETE,
        "Recency: snapshot_date - last_active_date, in days.", valid_min=0,
    ),
]

MODELING_SCHEMA = RAW_SCHEMA.extended(ENGINEERED_SPECS)
