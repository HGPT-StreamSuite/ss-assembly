# Verification evidence

This release is a new MRE boundary implementation, not a copy of StreamSuite or a feature-parity claim.

## Local Windows verification

uv 0.9.22 / Python 3.11.14. Each repository: uv add dependencies/dev extras, uv sync --locked --all-extras, uv run pytest, installed CLI demo, uv build. Tests use synthetic packaged fixtures and independent temporary/state databases. This initial local pass used editable sibling sources before release conversion to immutable Git dependencies.

| Repo | Tests | Installed CLI | Wheel build |
|---|---|---|---|
| ss-contracts | 9 passed in 0.27s | OK | OK |
| ss-context-store | 5 passed in 0.43s | OK | OK |
| ss-evidence | 6 passed in 0.36s | OK | OK |
| ss-prompt | 5 passed in 0.32s | OK | OK |
| ss-llm-client | 5 passed in 0.57s | OK | OK |
| ss-answer | 7 passed in 0.59s | OK | OK |
| ss-session-source | 7 passed in 0.75s | OK | OK |
| ss-archive-sink | 5 passed in 0.53s | OK | OK |
| ss-platform-sink | 6 passed in 0.55s | OK | OK |
| ss-speech-sink | 7 passed in 0.58s | OK | OK |
| ss-surface-sink | 7 passed in 0.56s | OK | OK |
| ss-assembly | 6 passed, 2 skipped in 1.20s | OK | OK |

Later storage CLI coverage adds a missing-DB query test. Final publishing re-runs tests/builds with remote Git dependencies. GitHub Actions runs every repo in a clean Ubuntu checkout; ss-assembly additionally starts an isolated real RabbitMQ 4.1.4 service and runs AMQP fanout/replay/outbox tests. Consult the Actions runs for their actual results.

## Production limits

Real platform delivery, spoken TTS/system playback, Lens WebSocket ingest, native/Spout surfaces, governed long-term knowledge and full production operating controls are outside this first MRE. Adapters are explicit, injectable and independently replaceable. No production credentials, personal data or live stream connections are used.
