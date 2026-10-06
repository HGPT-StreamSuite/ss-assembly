# ss-assembly

Pinned composition, topology setup and cross-repository verification.

StreamSuite 責任邊界重構的獨立 MRE，從零實作；不是既有專案的程式碼搬移，也不是完整功能移植。

## Quick start

```powershell
uv sync --locked
uv run ss-assembly demo
# Inspect five independent state DBs and safe HTML in a fresh directory:
uv run ss-assembly demo --state-dir state/inspection
uv run ss-assembly demo --fixture examples/demo.json
uv run pytest
uv build
```

The fixture is also packaged inside the wheel. Each repository installs and runs independently with its Git-pinned dependencies; sibling checkouts are not required.

## Python API and installation

```powershell
uv add "ss-assembly @ git+https://github.com/HGPT-StreamSuite/ss-assembly.git@v0.1.0"
```

Import `ss_assembly.core` for the public MRE API. Git dependency sources and resolved commit identities are recorded in `pyproject.toml` and `uv.lock`. No editable sibling paths are published.

## Responsibility and limitations

Owns reproducible dependency composition, topology configuration and verification fixtures. Has no business-event publisher or subscriber. Offline scenario wires public APIs through a collecting publisher and independent sink handlers; opt-in tests verify actual AMQP fanout, manual ACK, redelivery and unroutable outbox behavior. Broker topology setup declares durable queues/exchanges only.

See [BOUNDARY.md](BOUNDARY.md) for ownership and forbidden operations.
Fixtures are synthetic and offline by default. Platform sender, playback and model substitutes are explicitly labeled; passing tests does not validate Twitch/YouTube delivery, real speech or OBS output.

## RabbitMQ

```powershell
uv sync --locked --extra rabbitmq
```

Use an isolated development broker/vhost. No connection is made by `demo` or default tests. Default exchange is `ss.mre.events`; topology declarations do not alter StreamSuite exchanges. Source uses mandatory persistent publication and publisher confirms. Sinks use named durable queues, prefetch=1, manual ACK after handling and individual DLQs. Routing does not guarantee sink completion; delivery is at-least-once. Failed handlers are rejected to DLQ, not silently acknowledged.

Scope validation precedes application effects. Use one consumer process per state directory and a separate state directory per profile/session. Consumer queues default to `<repo>.<profile-id>`; use isolated vhosts for separate profiles, and do not run simultaneous sessions on the same queue.

## Composition verification

```powershell
uv run ss-assembly demo
# Inspect five independent state DBs and safe HTML in a fresh directory:
uv run ss-assembly demo --state-dir state/inspection
uv run --extra rabbitmq ss-assembly topology --profile-id fixture-profile
# Only this opt-in environment variable enables real-broker tests.
$env:SS_MRE_TEST_AMQP_URL = 'amqp://guest:guest@127.0.0.1/'
uv run --extra rabbitmq pytest -m integration
```

The broker tests generate unique exchanges/queues and clean up only their own resources. They publish synthetic records and verify independent fanout, duplicate processing, manual ACK and unroutable outbox retention. They do not connect to production streaming platforms.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for both diagrams and [docs/VERIFICATION.md](docs/VERIFICATION.md) for release evidence.

GitHub Actions includes an isolated RabbitMQ 4.1.4 service job; local default runs skip AMQP tests when no test URL is supplied.

See [all 12 repositories](docs/REPOSITORIES.md) for the complete MRE index.

For hands-on validation, follow the [step-by-step manual testing guide](docs/MANUAL_TESTING_GUIDE.md): individual repos, offline handoffs, uv/API composition, RabbitMQ fanout, recovery experiments and real adapters.
