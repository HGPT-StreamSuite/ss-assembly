# ss-assembly boundary

Role: **composition**. Public contract version: **1**.

Owns reproducible dependency composition, topology configuration and verification fixtures. Has no business-event publisher or subscriber. Offline scenario wires public APIs through a collecting publisher and independent sink handlers; opt-in tests verify actual AMQP fanout, manual ACK, redelivery and unroutable outbox behavior. Broker topology setup declares durable queues/exchanges only.

## Dependencies

Direct capability dependencies: ss-contracts, ss-session-source, ss-archive-sink, ss-platform-sink, ss-speech-sink, ss-surface-sink, ss-context-store, ss-llm-client.
Cross-repository imports use public package APIs, never another repository's tests, private SQL tables, runtime application internals or StreamSuite code.

## Invariants

- Library/composition repositories do not publish or subscribe to business events.
- ss-session-source publishes only. Sink applications consume only.
- Sink completion, failure and health stay in local state/CLI; no feedback events.
- Broker ACK/NACK and broker-managed DLQ routing are transport operations, not application business publication.
- Every event has explicit profile/channel/session scope, stable event identity and schema version.
- Public answer events exclude private prompt, retrieved context and diagnostic content.
- Synthetic fixtures use no personal records, credentials, production database or live platform connection.

## Verification

`uv run pytest` tests public behavior and installed CLI. Opt-in AMQP tests live in ss-assembly.
Passing these MRE tests does not establish production readiness or preserve every legacy feature.
