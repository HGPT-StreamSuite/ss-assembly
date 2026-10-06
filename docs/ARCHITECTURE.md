# Proposed MRE architecture

依賴圖的箭頭是「相依方 → 被依賴方」。虛線表示共同型別或組合啟動；RabbitMQ 線是通訊相依。
CLI argument parsing is local invocation, not a legacy routing module.

```mermaid
flowchart TB
    Assembly["ss-assembly"]
    subgraph Components["業務 repo：共同依賴 ss-contracts"]
        Source["ss-session-source：只發布"]
        Archive["ss-archive-sink：只消費"]
        Platform["ss-platform-sink：只消費"]
        Speech["ss-speech-sink：只消費"]
        Surface["ss-surface-sink：只消費"]
        Answer["ss-answer"]
        Store["ss-context-store"]
        Evidence["ss-evidence"]
        Prompt["ss-prompt"]
        LLM["ss-llm-client"]
        Source -->|uv| Answer
        Answer -->|uv：唯讀| Store
        Answer -->|uv| Evidence
        Answer -->|uv| Prompt
        Answer -->|uv| LLM
        Archive -->|uv：寫入| Store
        Surface -->|uv：冷啟動| Store
    end
    Components -.->|uv| Contracts["ss-contracts"]
    MQ[(RabbitMQ)]
    Source -->|RabbitMQ：發布| MQ
    Archive -->|RabbitMQ：訂閱| MQ
    Platform -->|RabbitMQ：訂閱| MQ
    Speech -->|RabbitMQ：訂閱| MQ
    Surface -->|RabbitMQ：訂閱| MQ
    Assembly -.->|uv／啟動| Source
    Assembly -.->|uv／啟動| Archive
    Assembly -.->|uv／啟動| Platform
    Assembly -.->|uv／啟動| Speech
    Assembly -.->|uv／啟動| Surface
```

資料圖的箭頭是「資料來源 → 接收者」。藍色雙框是 repo，黃色是資料，灰色是外部來源／輸出，紫色是 Broker。
同一 repo 可分成多個執行階段；兩個 DB 節點是相同資料在不同時間的狀態。

```mermaid
flowchart TB
    External["外部輸入／fixture"] --> Receive[["ss-session-source：接收與正規化"]]
    Receive --> Input["本輪輸入"]
    Input --> Prepare[["ss-answer：選擇資料"]]
    Input --> Publish[["ss-session-source：outbox 與發布"]]
    OldDB[("已保存的上下文")] --> Read[["ss-context-store：唯讀快照"]]
    Read --> Prepare
    Search["外部資料／fixture"] --> Evidence[["ss-evidence"]]
    Evidence --> Prompt[["ss-prompt"]]
    Prepare --> Prompt
    Prompt --> LLM[["ss-llm-client"]]
    LLM --> Finish[["ss-answer：輸出檢查"]]
    Evidence --> Finish
    Finish --> Publish
    Publish --> MQ[(RabbitMQ)]
    MQ --> Archive[["ss-archive-sink"]]
    Archive --> Write[["ss-context-store：受控寫入"]]
    Write --> NewDB[("更新後的上下文：後續輪次")]
    MQ --> Platform[["ss-platform-sink"]]
    Platform --> PlatformOut["平台 sender：MRE 使用替身"]
    MQ --> Speech[["ss-speech-sink"]]
    Speech --> Audio["播放 adapter：MRE 使用替身"]
    MQ --> Surface[["ss-surface-sink"]]
    Read -->|冷啟動| Surface
    Surface --> Screen["安全 HTML"]
    classDef repo fill:#DBEAFE,stroke:#2563EB,stroke-width:2px,color:#172554;
    classDef external fill:#F3F4F6,stroke:#6B7280,color:#111827;
    classDef data fill:#FEF3C7,stroke:#D97706,color:#78350F;
    classDef broker fill:#EDE9FE,stroke:#7C3AED,stroke-width:2px,color:#4C1D95;
    class Receive,Read,Evidence,Prepare,Prompt,LLM,Finish,Publish,Archive,Write,Platform,Speech,Surface repo;
    class External,Search,PlatformOut,Audio,Screen external;
    class Input,OldDB,NewDB data;
    class MQ broker;
```

## Ownership

- Context schema/migrations/read/write API: ss-context-store. Event-driven context writes: ss-archive-sink only.
- Input cache and event outbox: ss-session-source/source.db, separate from context.
- Delivery checkpoints: ss-platform-sink/delivery.db; playback: ss-speech-sink/speech.db; projection: ss-surface-sink/surface.db.
- Store reader returns an explicit as-of snapshot. Current input is passed directly to answer, without waiting for archive feedback.
- Assembly configures infrastructure and installs pinned packages; it owns no business data.

## First MRE scope

This release proves the boundaries with deterministic fixtures and opt-in AMQP adapters.
Long-term governed facts, entity knowledge, multi-turn clarification, loyalty/games, scheduling, WebSocket Lens ingest, actual platform/TTS/Spout adapters and production operating controls need separate capability MREs or later extensions. No feature parity claim is made.
