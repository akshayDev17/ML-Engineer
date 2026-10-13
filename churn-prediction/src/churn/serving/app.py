"""Minimal online endpoint (M12): FastAPI shell around `ChurnPredictor`.

    CHURN_BUNDLE=artifacts/registry/churn-model/v1 uvicorn churn.serving.app:app --port 8000

The predictor (ONNX session + fitted preprocessor) is loaded ONCE at startup, never per
request; the request schema is explicit and every field is optional because the cleaner and
imputers handle gaps exactly as they did in training.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from churn.serving.bundle import LocalModelRegistry
from churn.serving.predictor import ChurnPredictor

_state: dict[str, ChurnPredictor] = {}


class CustomerRecord(BaseModel):
    customer_id: str | None = None
    transaction_amount: float | str | None = None
    contract_type: str | None = None
    payment_method: str | None = None
    last_active_date: str | None = None
    tenure_months: float | str | None = None
    monthly_charges: float | str | None = None
    total_charges: float | str | None = None
    num_support_tickets: float | None = None
    num_products: float | None = None
    age: float | None = None
    avg_session_minutes: float | None = None
    discount_pct: float | None = None
    satisfaction_score: str | None = None
    customer_tier: str | None = None
    income_bracket: str | None = None
    region: str | None = None
    acquisition_channel: str | None = None
    is_paperless_billing: str | bool | None = None
    marketing_emails_opened: float | None = None


class PredictRequest(BaseModel):
    records: list[CustomerRecord]
    as_of: str | None = None  # defaults to today


def _bundle_dir() -> Path:
    if os.environ.get("CHURN_BUNDLE"):
        return Path(os.environ["CHURN_BUNDLE"])
    return LocalModelRegistry(os.environ.get("CHURN_REGISTRY", "artifacts/registry"), "churn-model").latest_dir()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _state["predictor"] = ChurnPredictor.load(_bundle_dir(), backend=os.environ.get("CHURN_BACKEND", "onnx"))
    yield
    _state.clear()


app = FastAPI(title="churn-model", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    meta = _state["predictor"].metadata
    return {"status": "ok", "model": meta.model_name, "version": meta.version, "threshold": meta.threshold}


@app.post("/predict")
def predict(request: PredictRequest) -> dict:
    records = [r.model_dump() for r in request.records]
    return {"predictions": _state["predictor"].predict(records, as_of=request.as_of)}
