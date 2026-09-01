"""Batch ingestion job: validate a raw transaction file and split it.

Real pipeline shape: read a batch -> run the gate -> land valid rows in the
clean sink and invalid rows in quarantine, with the violation report
alongside. In production this is scheduled (cron / Airflow / Prefect);
here it's a CLI.

Usage:
    python run_batch.py --input data/transactions_contaminated.csv
"""

import argparse
import logging
from pathlib import Path

from gates.batch_ingestion import validate_batch
from ingest import read_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_batch")


def main() -> None:
    p = argparse.ArgumentParser(description="Validate one raw transaction batch.")
    p.add_argument("--input", required=True)
    p.add_argument("--clean-out", default="out/batch_clean.csv")
    p.add_argument("--quarantine-out", default="out/batch_quarantine.csv")
    p.add_argument("--failures-out", default="out/batch_failures.csv")
    args = p.parse_args()

    Path(args.clean_out).parent.mkdir(parents=True, exist_ok=True)

    raw = read_transactions(args.input)
    log.info("read %d raw rows from %s", len(raw), args.input)

    result = validate_batch(raw)

    result.valid.to_csv(args.clean_out, index=False)
    if result.is_clean:
        log.info("batch is CLEAN — no quarantine written")
    else:
        result.invalid.to_csv(args.quarantine_out, index=False)
        result.failure_cases.to_csv(args.failures_out, index=False)
        log.info("quarantine -> %s", args.quarantine_out)
        log.info("violations -> %s", args.failures_out)

    log.info("metrics: %s", result.metrics())
    log.info("clean -> %s", args.clean_out)


if __name__ == "__main__":
    main()
