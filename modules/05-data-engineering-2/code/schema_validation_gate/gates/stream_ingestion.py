"""Validates each micro-batch window of the transaction stream, publishing clean events onward and invalid events to a dead-letter queue, without ever blocking the stream."""

from gates.batch_ingestion import validate_batch


def process_window(
    window_df,
    publish_clean,
    publish_dlq,
) -> None:
    """Validate one stream window and route it. Never blocks/raises.

    Sinks are injected for testability (a real deployment passes Kafka
    producers; a test passes list-capturing callables). Note: uniqueness
    is *window-local* — cross-window dedup is a downstream concern.
    """
    result = validate_batch(window_df)
    publish_clean(result.valid)
    if not result.is_clean:
        publish_dlq(result.invalid, result.failure_cases)
    # metrics hook: result.metrics() -> M15 pillar-2 dashboard/alert
