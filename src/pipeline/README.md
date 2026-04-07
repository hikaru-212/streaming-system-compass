# Pipeline Layer

This layer is responsible for processing events from the event log.

## Responsibilities

- Consume events from the event stream
- Apply business logic
- Produce deterministic state transitions

## Scope

- Transactional correctness is prioritized over performance
- The pipeline must support idempotent processing
- Ordering is guaranteed per entity (e.g., per order_id)

## Non-goals

- Global ordering across all events
- Distributed coordination or consensus
- Long-term analytical aggregation

## Future Work

- Out-of-order event handling
- Replay support
- Failure recovery integration