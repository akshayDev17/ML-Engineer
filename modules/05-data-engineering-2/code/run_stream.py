"""Stream ingestion consumer: validate each window and route it.

Real pipeline shape: subscribe to a stream, and for each micro-batch window
run the gate, forward clean rows onward and invalid rows to the dead-letter
queue. In production the publishers are Kafka producers; here they append to
files. The gate never blocks the stream.

Usage:
    python run_stream.py --input data/transactions_contaminated.csv
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

from gates.stream_ingestion import process_window
from ingest import DTYPES, PARSE_DATES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_stream")


def main() -> None:
    p = argparse.ArgumentParser(description="Consume the transaction feed window-by-window.")
    p.add_argument("--input", required=True)
    p.add_argument("--window-size", type=int, default=50)
    p.add_argument("--clean-out", default="out/stream_clean.csv")
    p.add_argument("--dlq-out", default="out/stream_dlq.csv")
    args = p.parse_args()

    clean_path = Path(args.clean_out)
    dlq_path = Path(args.dlq_out)
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    clean_path.unlink(missing_ok=True)
    dlq_path.unlink(missing_ok=True)

    def publish_clean(df: pd.DataFrame) -> None:
        df.to_csv(clean_path, mode="a", header=not clean_path.exists(), index=False)

    def publish_dlq(df: pd.DataFrame, failure_cases: pd.DataFrame) -> None:
        df.to_csv(dlq_path, mode="a", header=not dlq_path.exists(), index=False)
        log.info("DLQ: %d bad rows; checks=%s", len(df), sorted(set(failure_cases["check"])))

    # a file-backed stream: windows arrive the way a consumer receives them
    reader = pd.read_csv(
        args.input, dtype=DTYPES, parse_dates=PARSE_DATES, chunksize=args.window_size
    )
    for i, window in enumerate(reader):
        process_window(window, publish_clean, publish_dlq)
        log.info("window %d: %d rows processed", i, len(window))

    log.info("clean -> %s", clean_path)
    log.info("dlq   -> %s", dlq_path)


if __name__ == "__main__":
    main()
