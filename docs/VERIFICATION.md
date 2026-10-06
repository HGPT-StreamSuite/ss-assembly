# Published MRE verification

Verified on **2026-10-07 (Asia/Taipei)**. All 12 repositories are Public under HGPT-StreamSuite, use remote main, and have a v0.1.0 tag. Code was committed on local codex/mre-foundation branches with `feat: add independently verifiable MRE boundary`. No StreamSuite source or live data was copied; the original workspace was not modified by this task.

## Release checks

- **79 offline tests passed** across 12 independent Windows environments. The assembly repository additionally skipped its 3 opt-in Broker tests locally because no local AMQP listener was available.
- Every repository passed installed console-entrypoint and module-entrypoint tests, fixture replay and wheel/sdist build.
- Final synchronization and verification used `uv add --raw` with immutable Git commit requirements, `uv sync --locked --all-extras --no-sources`, `uv run pytest`, CLI demo and `uv build`.
- Every repository passed clean Linux GitHub Actions verification with its remote Git dependencies.
- **3 real RabbitMQ tests passed** in ss-assembly's isolated RabbitMQ 4.1.4 GitHub service job: independent fanout/replay/manual ACK; unroutable publication preserves the source outbox; wrong scope is rejected to DLQ with no archive side effect.
- A fresh, non-Git consumer project used a single `uv add` of ss-assembly from its release commit, then successfully ran **all 12 installed CLIs**. It had no sibling source overrides. Persistent composed replay produced independent state files and safe surface.html.

## Repository evidence

| Repository | Local tests | Release code commit | GitHub CI |
|---|---|---|---|
| [ss-contracts](https://github.com/HGPT-StreamSuite/ss-contracts) | 9 passed in 0.32s | [3dca4edf](https://github.com/HGPT-StreamSuite/ss-contracts/commit/3dca4edfb434911d0a27bf1db390442bc3489c27) | [passed](https://github.com/HGPT-StreamSuite/ss-contracts/actions/runs/37492635396) |
| [ss-context-store](https://github.com/HGPT-StreamSuite/ss-context-store) | 9 passed in 0.62s | [0938158b](https://github.com/HGPT-StreamSuite/ss-context-store/commit/0938158b75669243c596c40a17aa2dff70bd7edc) | [passed](https://github.com/HGPT-StreamSuite/ss-context-store/actions/runs/37492671508) |
| [ss-evidence](https://github.com/HGPT-StreamSuite/ss-evidence) | 6 passed in 0.34s | [4e0985e6](https://github.com/HGPT-StreamSuite/ss-evidence/commit/4e0985e61b98793386a5f9ab7c62909eda4cd4b4) | [passed](https://github.com/HGPT-StreamSuite/ss-evidence/actions/runs/37492696187) |
| [ss-prompt](https://github.com/HGPT-StreamSuite/ss-prompt) | 5 passed in 0.52s | [6b6d366c](https://github.com/HGPT-StreamSuite/ss-prompt/commit/6b6d366c34ef0c8f961473d05f0838bcc5574c91) | [passed](https://github.com/HGPT-StreamSuite/ss-prompt/actions/runs/37492728614) |
| [ss-llm-client](https://github.com/HGPT-StreamSuite/ss-llm-client) | 5 passed in 0.62s | [ce170dd6](https://github.com/HGPT-StreamSuite/ss-llm-client/commit/ce170dd63b394e36ae1cf3614fbe3e3c2bdce252) | [passed](https://github.com/HGPT-StreamSuite/ss-llm-client/actions/runs/37492753610) |
| [ss-answer](https://github.com/HGPT-StreamSuite/ss-answer) | 7 passed in 0.77s | [88e238aa](https://github.com/HGPT-StreamSuite/ss-answer/commit/88e238aa202bfbed912e78a4b6d2435599c56cd7) | [passed](https://github.com/HGPT-StreamSuite/ss-answer/actions/runs/37492790278) |
| [ss-session-source](https://github.com/HGPT-StreamSuite/ss-session-source) | 7 passed in 0.91s | [d0ad4411](https://github.com/HGPT-StreamSuite/ss-session-source/commit/d0ad4411f29451bede3fe8a7a182f3696a06ba5e) | [passed](https://github.com/HGPT-StreamSuite/ss-session-source/actions/runs/37492844626) |
| [ss-archive-sink](https://github.com/HGPT-StreamSuite/ss-archive-sink) | 5 passed in 0.70s | [6c12faea](https://github.com/HGPT-StreamSuite/ss-archive-sink/commit/6c12faeae4c4726ec631a6c09ffa5048dad72eb7) | [passed](https://github.com/HGPT-StreamSuite/ss-archive-sink/actions/runs/37492868150) |
| [ss-platform-sink](https://github.com/HGPT-StreamSuite/ss-platform-sink) | 6 passed in 0.67s | [94a6ccdc](https://github.com/HGPT-StreamSuite/ss-platform-sink/commit/94a6ccdccabb8ff537f84272a0527001c0adfec7) | [passed](https://github.com/HGPT-StreamSuite/ss-platform-sink/actions/runs/37492900028) |
| [ss-speech-sink](https://github.com/HGPT-StreamSuite/ss-speech-sink) | 7 passed in 0.66s | [a43fc2b8](https://github.com/HGPT-StreamSuite/ss-speech-sink/commit/a43fc2b86403e93c0e801d29e5b0c02014e88945) | [passed](https://github.com/HGPT-StreamSuite/ss-speech-sink/actions/runs/37492936567) |
| [ss-surface-sink](https://github.com/HGPT-StreamSuite/ss-surface-sink) | 7 passed in 0.62s | [b23f2711](https://github.com/HGPT-StreamSuite/ss-surface-sink/commit/b23f2711c2bc982cfc6cc7520607a1852b961a91) | [passed](https://github.com/HGPT-StreamSuite/ss-surface-sink/actions/runs/37492956344) |
| [ss-assembly](https://github.com/HGPT-StreamSuite/ss-assembly) | 6 passed, 3 skipped in 1.34s | [6cb188df](https://github.com/HGPT-StreamSuite/ss-assembly/commit/6cb188df19804ab19860e6e91e121900e894a760) | [passed](https://github.com/HGPT-StreamSuite/ss-assembly/actions/runs/37493001868) |

Tags identify the initial code release. Later documentation-only commits do not change the tagged implementation or its pinned dependency graph. Detailed package-local evidence is in each repository's VERIFICATION.json.

## Reproduce the composition

In a new uv project:

```powershell
uv add --raw "ss-assembly @ git+https://github.com/HGPT-StreamSuite/ss-assembly.git@v0.1.0"
uv run ss-assembly demo
uv run ss-assembly demo --state-dir state/inspection
```

Clone a single repository to run its tests:

```powershell
uv sync --locked
uv run pytest
```

For isolated real-Broker verification from an ss-assembly checkout:

```powershell
uv sync --locked --extra rabbitmq
$env:SS_MRE_TEST_AMQP_URL = 'amqp://guest:guest@127.0.0.1/'
uv run --extra rabbitmq pytest -m integration -v
```

## Scope of this release

This is a new boundary MRE, not full product feature parity. Evidence search defaults to recorded fixtures; platform senders and playback are explicitly replaceable substitutes. The audio file adapter produces a synthetic tone, not spoken TTS. Surface output is safe standalone HTML, not native/Spout rendering. Optional real Ollama calling and actual AMQP adapters are included; no real model, streaming platform, audio capture or OBS environment was used during these checks. Governed long-term knowledge, entity graph, multi-turn clarification, loyalty/games and scheduling require later MRE extensions.
