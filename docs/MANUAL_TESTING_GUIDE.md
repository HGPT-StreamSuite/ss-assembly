# MRE 人工驗收與階段整合指南

本指南以 12 個 repo 的 **v0.1.0** 為基準，使用 Windows PowerShell 與 uv。建議依序完成「單 repo → 離線資料交接 → Python API 組合 → RabbitMQ 跨行程 → 故障復原 → 真實 adapter」。每一階段先保存證據，再決定是否前進；先不要把所有服務一次開起來。

目標是能親自說明：每個 repo 接受什麼輸入、產生什麼輸出、擁有哪些狀態，以及失敗後由誰負責重試。這份指南驗證新邊界，不以重現舊專案邏輯為通過條件。

相關文件：[架構圖](ARCHITECTURE.md)、[repo 清單](REPOSITORIES.md)、[既有驗證紀錄](VERIFICATION.md)。撰寫日期：2026-10-07。

## 0. 先界定「通過」代表什麼

目前多數外部功能採測試替身：

| 功能 | v0.1.0 可觀察的行為 | 尚未代表 |
| --- | --- | --- |
| 搜尋 | FixtureProvider 篩選合成 evidence | 真實搜尋服務可用、內容可信 |
| 回答模型 | FixtureClient 回傳指定文字；另有 OllamaClient API | 改問題會產生智慧回答、回答正確 |
| 平台送達 | RecordingSender 或 FileSender 留下分段紀錄 | Twitch／YouTube 已收到訊息 |
| 語音 | RecordingPlayer 或 ToneFilePlayer 產生短音調 WAV | 真正 TTS、音效裝置已播放 |
| 畫面 | 安全跳脫的 HTML 檔案 | OBS／Spout、即時視窗或自動刷新 |
| STT 輸入 | 已完成逐字稿與音源 attestation 的合成輸入 | WASAPI 裝置驗收、實際轉錄 |

先驗輸入／輸出契約與狀態，再驗外部 adapter。標記「替身驗收通過」或「尚未實作」，不要把它們寫成真實服務通過。

邊界規則：`ss-session-source` 僅發布業務事件；四個 sink 僅消費業務事件；六個 library 不自行使用 RabbitMQ；`ss-assembly` 管理組合與 topology。Broker 的 ACK／DLQ 機制不算 sink 對外發布業務事件。

## 1. 建立可保留的人工實驗工作區

原始 MRE 在暫存資料夾，人工紀錄建議放在長期保存的位置。下面使用全新的 `C:/dev/ss-mre-lab`；若已存在，改用另一個名稱，保留舊實驗。

```powershell
$MreLab = 'C:/dev/ss-mre-lab'
if (Test-Path $MreLab) { throw '請改用尚未存在的實驗目錄' }
New-Item -ItemType Directory -Path "$MreLab/repos", "$MreLab/fixtures", "$MreLab/evidence", "$MreLab/state", "$MreLab/experiments" | Out-Null
$env:PYTHONUTF8 = '1'
git --version
uv --version
uv python list

$RepoNames = @(
  'ss-contracts', 'ss-context-store', 'ss-evidence', 'ss-prompt',
  'ss-llm-client', 'ss-answer', 'ss-session-source', 'ss-archive-sink',
  'ss-platform-sink', 'ss-speech-sink', 'ss-surface-sink', 'ss-assembly'
)
foreach ($RepoName in $RepoNames) {
  git clone --branch v0.1.0 "https://github.com/HGPT-StreamSuite/$RepoName.git" "$MreLab/repos/$RepoName"
  if ($LASTEXITCODE -ne 0) { throw "clone 失敗：$RepoName" }
  git -C "$MreLab/repos/$RepoName" switch -c codex/manual-validation
}
```

記錄 uv、Python 與各 repo 的 `git rev-parse HEAD`。既有發布驗證使用 uv 0.9.22／Python 3.11.14；可先以 Python 3.11 作為基準。每個 repo 使用自己的 `.venv` 與 `uv.lock`。

**通過條件：** 12 個 checkout 有明確版本；資料與紀錄不放在原專案或共享正式狀態目錄。

後續 PowerShell 區塊沿用 `$MreLab`。每個新終端先重新設定它與 `PYTHONUTF8`。建立 JSON 請使用下列函式，避免 Windows PowerShell 5 的 UTF-8 BOM 被 Python JSON parser 拒絕：

```powershell
function Write-LabJson {
  param([string]$Path, $Value)
  [System.IO.File]::WriteAllText(
    $Path, ($Value | ConvertTo-Json -Depth 40),
    [System.Text.UTF8Encoding]::new($false)
  )
}
```

## 2. 逐一認識 repo：一次只驗一個

對每個 repo 依序執行下列流程；將 `ss-contracts` 換成當次名稱：

```powershell
$RepoName = 'ss-contracts'
Set-Location "$MreLab/repos/$RepoName"
Get-Content README.md
Get-Content BOUNDARY.md
uv sync --locked --python 3.11
uv run $RepoName --help
uv run $RepoName demo
uv run $RepoName demo --fixture examples/demo.json
uv run pytest -m 'not integration'
```

將 CLI 結果、人工觀察與測試結果分開記錄。需要保存輸出時：

```powershell
$DemoLines = uv run $RepoName demo 2> "$MreLab/evidence/$RepoName-demo.stderr.txt"
$DemoExit = $LASTEXITCODE
[System.IO.File]::WriteAllText("$MreLab/evidence/$RepoName-demo.json", ($DemoLines -join "`n"), [System.Text.UTF8Encoding]::new($false))
$DemoResult = ($DemoLines -join "`n") | ConvertFrom-Json
$DemoResult | Format-List
```

`demo` 大多使用隨後清除的暫存狀態，重跑相同指令不是跨行程持久化測試。消費 CLI 可能回傳 `ok: false` 卻結束碼為 0，因此同時看 JSON、結束碼與外部效果。

| Repo／角色 | 預設 demo 應觀察到 | 自訂案例／責任問題 |
| --- | --- | --- |
| ss-contracts／library | envelope 正規化與穩定 event_id | schema_version 改為 2、payload 加 prompt 應拒絕；哪些欄位允許公開？ |
| ss-context-store／library | 3 個 scoped events 的 snapshot | 重複寫入不新增；其他 scope／截止時間看不到資料 |
| ss-evidence／library | 一筆合成標題 evidence，headline_only 的 excerpt 為空 | published_at 改為 0 時過期；缺證用 gaps 表達 |
| ss-prompt／library | system／user／used_chars／omitted | 放大可選 context，應整塊省略；問題本身超預算應拒絕 |
| ss-llm-client／library | fixture-model 與固定 response | 改 response 能改輸出；逾時與錯誤用第 7 步 API 注入 |
| ss-answer／library | 標題不足以支撐內文問題時，仍呼叫模型一次，再 fallback | 清空 evidence，觀察缺證仍呼叫模型；查 diagnostics，不把它發布 |
| ss-session-source／publisher | live／transcript／chat／answer 共 4 events，model_calls=1 | 音源與 attestation 不符應拒絕；誰擁有 outbox？ |
| ss-archive-sink／consumer | 前三筆 inserted=true，重複聊天 false；snapshot 3 筆 | 異 scope 拒絕；只寫 archive，不生成回答 |
| ss-platform-sink／consumer | 長回答分 3 段；重複 event 新送出 0 段 | 第 2 段失敗後從 checkpoint 恢復，見第 7 步 |
| ss-speech-sink／consumer | queued、duplicate；播放紀錄一筆 | now 改為 1061，應過期、不播放 |
| ss-surface-sink／consumer | 重複不新增；HTML 跳脫不可信文字 | `<script>` 不執行；cold_start 不載入私人回答歷史 |
| ss-assembly／composition | 首次 4 events、一次模型／送達／播放 | 同 state 重跑不新增；不把 topology 當業務流程 |

**通過條件：** 每個 repo 至少做一個正常案例、一個邊界／失敗案例，並用自己的話寫下輸入、輸出、持久狀態、禁止操作。不理解的 repo 先停在本階段。

## 3. 手改 fixture，確認功能確實受輸入控制

永遠複製到 `fixtures` 再改，不覆寫發布版本的 fixture。例如語音過期：

```powershell
Set-Location "$MreLab/repos/ss-speech-sink"
$SpeechCase = Get-Content examples/demo.json -Raw | ConvertFrom-Json
$SpeechCase.now = 1061
Write-LabJson "$MreLab/fixtures/speech-expired.json" $SpeechCase
uv run ss-speech-sink demo --fixture "$MreLab/fixtures/speech-expired.json"
```

預期沒有播放紀錄；同一事件仍可被判為 duplicate。這是 expiry 機制的成功案例，不是播放器失敗。

再驗三個重要界線：

1. `ss-contracts` fixture 的 `event.schema_version=2`，應結束碼 2；把值還原後才能前進。
2. `ss-evidence` fixture 的 `items[0].published_at=0`，應無 usable evidence，帶有時間窗／缺證 gap。
3. `ss-prompt` fixture 放入很大的 context，維持合理 char_budget，應在 `omitted` 看到 context。這是字元預算，不是實際 token 計數；保留 question 的必要內容。

CLI 只使用已實作的 fixture 欄位：`ss-llm-client demo` 不讀取 delay／error；`ss-answer demo` 不注入 context reader，也不使用 JSON 中的 char_budget。這些實驗用第 7 步的 Python API，避免「改了但沒有作用」被誤判為功能成功。

## 4. 獨立驗證 Context Store 的資料所有權

這一步使用明確保留的 SQLite，而不是 demo 暫存 DB：

```powershell
Set-Location "$MreLab/repos/ss-context-store"
$ContextCase = Get-Content examples/demo.json -Raw | ConvertFrom-Json
$ContextDb = "$MreLab/state/context-only.db"
Write-LabJson "$MreLab/fixtures/one-event.json" $ContextCase.events[0]
uv run ss-context-store init --db $ContextDb
uv run ss-context-store record --db $ContextDb --event "$MreLab/fixtures/one-event.json"
uv run ss-context-store record --db $ContextDb --event "$MreLab/fixtures/one-event.json"
uv run ss-context-store query --db $ContextDb --profile-id fixture-profile --channel-id fixture-channel --session-id fixture-session --as-of 1001 --user-id fixture:user-1
uv run ss-context-store query --db $ContextDb --profile-id fixture-profile --channel-id fixture-channel --session-id fixture-session --as-of 999 --user-id fixture:user-1
uv run ss-context-store query --db $ContextDb --profile-id other-profile --channel-id fixture-channel --session-id fixture-session --as-of 1001 --user-id fixture:user-1
```

預期第一次 inserted=true、第二次 false；查詢依序看到一筆、零筆、零筆。再透過 `record` 寫入 fixture 其餘兩筆，分別以 `fixture:user-1`、另一個 user、不指定 user 查詢：公共聊天／逐字稿可見，回答歷史只對相符 user 可見。

最後查詢一個尚不存在的 DB：應失敗，而且不能自動建立它。初始化與寫入是明確操作；snapshot 查詢唯讀。此 MRE 沒有實作長期觀眾事實、知識庫或 Mem0。

**通過條件：** scope、時間與 user 邊界符合預期；讀者不負責補建 DB。不要直接用 SQL 改狀態來「修正」結果。

## 5. 用檔案手動交接事件，先排除 RabbitMQ 變因

在 producer 產生一次事件，再把完全相同的事件交給各 sink demo。這會驗證資料契約，不驗持久 transport。

```powershell
Set-Location "$MreLab/repos/ss-session-source"
$SourceResult = (uv run ss-session-source demo | Out-String) | ConvertFrom-Json
if (-not $SourceResult.ok) { throw 'source 失敗' }
$SourceCase = Get-Content examples/demo.json -Raw | ConvertFrom-Json
$AllSinkCase = @{ scope = $SourceCase.scope; events = @($SourceResult.events) }
$AnswerSinkCase = @{
  scope = $SourceCase.scope
  events = @($SourceResult.events | Where-Object { $_.type -eq 'answer.completed' })
  now = 1003
}
Write-LabJson "$MreLab/fixtures/all-events.json" $AllSinkCase
Write-LabJson "$MreLab/fixtures/answer-events.json" $AnswerSinkCase

Set-Location "$MreLab/repos/ss-archive-sink"
uv run ss-archive-sink demo --fixture "$MreLab/fixtures/all-events.json"
Set-Location "$MreLab/repos/ss-surface-sink"
uv run ss-surface-sink demo --fixture "$MreLab/fixtures/all-events.json"
Set-Location "$MreLab/repos/ss-platform-sink"
uv run ss-platform-sink demo --fixture "$MreLab/fixtures/answer-events.json"
Set-Location "$MreLab/repos/ss-speech-sink"
uv run ss-speech-sink demo --fixture "$MreLab/fixtures/answer-events.json"
```

預期 archive／surface 各處理 4 個事件；platform／speech 各處理一個 answer。檢查同一 answer 的 event_id、trace_id、scope、text 在四個 sink 保持一致。對 platform 交接非 answer 應拒絕；不要為了讓它成功而修改 consumer 職責。

**通過條件：** sink 能接受 producer 實際輸出，不需要了解 producer 內部類別或 DB；公開 envelope 沒有 diagnostics、完整 prompt 或私人 context。

## 6. 驗證離線組合與跨行程持久化

```powershell
Set-Location "$MreLab/repos/ss-assembly"
uv sync --locked
uv run ss-assembly demo --state-dir "$MreLab/state/assembly-01"
uv run ss-assembly demo --state-dir "$MreLab/state/assembly-01"
Start-Process "$MreLab/state/assembly-01/surface.html"
```

| 指標 | 第一次 | 同 fixture／同 state 第二次 |
| --- | ---: | ---: |
| published／archived／surface_inserted | 各 4 | 各 0 |
| model_calls／delivered_parts／played | 各 1 | 各 0 |
| context_events | 4 | 4 |

檢視五份獨立 state：`source.db`、`context.db`、`delivery.db`、`speech.db`、`surface.db`。確認畫面文字與事件一致，HTML 需人工重新整理。

重要限制：此 scenario 先生成整批 source，再寫入 archive。因此首次批次中的後續回答，不代表已讀取同批剛發生的聊天。想驗 context reader，做第 7 步；想驗跨行程即時歸檔，做第 9 步。

此 demo 的最後 snapshot 固定使用 `as_of=2000`；保留預設 1000–1003 合成時間。不要把即時 RabbitMQ 用的當前時間 fixture 放進這個 demo，再以 context_events 判斷資料遺失。

再複製 fixture，修改既有 input 的正文、保留 id，使用同 state 重跑：應報 collision。新測資用新 id 與新 state；同一事件重播則保持整份 fixture 不變，包含 occurred_at。

**通過條件：** 重新啟動後資料保留，已完成效果不重做；新事件與事件重播能明確區分。

## 7. 在獨立 uv 專案人工組合 Python API

建立實驗專案，確認透過發布的 Git 相依能裝到全部入口：

```powershell
uv init --bare --python 3.11 "$MreLab/experiments/api-baseline"
Set-Location "$MreLab/experiments/api-baseline"
uv python pin 3.11
uv add --raw 'ss-assembly @ git+https://github.com/HGPT-StreamSuite/ss-assembly.git@6cb188df19804ab19860e6e91e121900e894a760'
uv tree
uv run ss-answer demo
uv run ss-assembly demo
```

`uv.lock` 保存解析版本。這個實驗沒有要求 sibling checkout；`ss-assembly` 的直接與遞迴相依帶入其他 repo。Git 相依及開發 sources 的差異見 [uv 文件](https://docs.astral.sh/uv/concepts/projects/dependencies/)。

將以下程式存為實驗專案的 `api_probe.py`，再執行 `uv run python api_probe.py`：

```python
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from importlib.resources import files
from ss_contracts.core import Scope, make_event
from ss_archive_sink.core import Archive
from ss_context_store.core import snapshot
from ss_answer.core import answer
from ss_llm_client.core import FixtureClient
from ss_platform_sink.core import Delivery, RecordingSender

async def main():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        scope = Scope("api-profile", "api-channel", "api-session")
        archive = Archive(root / "context.db", scope)
        seed = make_event(
            "chat.observed",
            {"user_id": "fixture:user-1", "text": "API_CONTEXT_MARKER", "platform": "fixture"},
            scope, "api-chat-1", 1000,
        )
        archive.handle(seed.as_dict())
        reader = lambda scoped, now, user: snapshot(archive.path, scoped, now, user_id=user)
        request = {"question": "剛才說了什麼？", "user_id": "fixture:user-1", "needs_context": True}
        client = FixtureClient("合成回答")
        result = await answer(request, scope, 1001, client, context_reader=reader)
        # Prompt 僅在本機檢查，不送到 broker／公開紀錄。
        assert "API_CONTEXT_MARKER" in result.diagnostics["prompt"]["user"]
        assert client.calls == 1
        for failing in (FixtureClient(error=True), FixtureClient(delay=0.1)):
            failure = await answer(request, scope, 1001, failing, context_reader=reader, timeout=0.01)
            assert failure.status == "fallback" and failing.calls == 1
        budget_client = FixtureClient()
        budget = await answer({"question": "太長" * 5000}, scope, 1001, budget_client, char_budget=100)
        assert budget.status == "fallback" and budget_client.calls == 0

        fixture = json.loads(files("ss_platform_sink").joinpath("fixtures/demo.json").read_text(encoding="utf-8"))
        platform_scope = Scope(**fixture["scope"])
        delivery_path = root / "delivery.db"
        first = RecordingSender(fail_part=2)
        try:
            Delivery(delivery_path, platform_scope, max_chars=32).handle(fixture["events"][0], first)
        except OSError:
            pass
        assert [part["part"] for part in first.sent] == [1]
        resumed = RecordingSender()
        outcome = Delivery(delivery_path, platform_scope, max_chars=32).handle(fixture["events"][0], resumed)
        assert [part["part"] for part in resumed.sent] == [2, 3]
        assert outcome["newly_sent"] == 2
        print("PASS: context injection; model failure/timeout; budget gate; partial resume")

asyncio.run(main())
```

**通過條件：** context 經 reader 契約注入，模型失敗有可見 fallback，必要 prompt 超預算不呼叫模型；分段重啟保留第一段 checkpoint。這些 API 實驗避免依賴其他 repo 私有 DB 表格。

實際 send 與 checkpoint 並非一個原子交易；「已送出但尚未記錄」的段落仍可能重複。語音的 started 狀態則避免自動重播不確定已播的項目。驗收時保留這些語意差異，不宣稱 exactly-once。

## 8. 準備隔離的 RabbitMQ 實驗環境

先準備開發用 RabbitMQ，依 [Windows 官方安裝文件](https://www.rabbitmq.com/docs/install-windows) 與 [Management 文件](https://www.rabbitmq.com/docs/management)。不使用原專案的 exchange／queue／DB。

可在 RabbitMQ 管理終端建立專用 vhost，例如：

```powershell
rabbitmqctl.bat add_vhost ss-mre-manual-01
rabbitmqctl.bat set_permissions -p ss-mre-manual-01 guest '.*' '.*' '.*'
```

這個例子限本機開發 broker 的既有 guest 帳號；其他帳號由你自己的 broker 設定決定。每個實驗終端設定：

```powershell
$MreLab = 'C:/dev/ss-mre-lab'
$env:PYTHONUTF8 = '1'
$env:SS_AMQP_URL = 'amqp://guest:guest@127.0.0.1/ss-mre-manual-01'
```

URI 不放進公開紀錄或 Git。vhost 隔離 exchanges／queues／bindings，詳見 [官方 vhost 文件](https://www.rabbitmq.com/docs/vhosts)。每階段另外使用新 profile、exchange 與 state 目錄：預設 queue 名是 `<repo>.<profile-id>`，不含 session／exchange，僅換 exchange 仍可能讓舊 queue 殘留 binding。

在 source 與各 sink checkout 執行 `uv sync --locked --extra rabbitmq`。組合 repo 的 topology／integration tests 也需要 rabbitmq extra。

**通過條件：** 能看到專用 vhost；有辦法在管理介面確認 bindings、consumer 數、ready／unacked 與 DLQ。若 broker 尚未可用，把此階段記為未執行，不影響前面離線階段的結論。

## 9. 第一個跨行程實驗：Source → Archive

先只啟動兩個角色。此階段不要執行完整 topology，避免另外三個未啟動 sink 的 queue 累積訊息。

**終端 A：archive。** 沿用第 8 步環境設定：

```powershell
Set-Location "$MreLab/repos/ss-archive-sink"
uv run --extra rabbitmq ss-archive-sink consume --exchange ss.mre.archive01 --profile-id manual-archive01 --channel-id manual-channel --session-id manual-session01 --state-dir "$MreLab/state/rabbit-archive01/archive" --limit 4 --idle-timeout 120
```

等待管理介面看到 `ss-archive-sink.manual-archive01` 有一個 consumer，再發布。CLI 不提供「已就緒」提示；不要單靠視窗已開啟來判斷。

**終端 B：source。** 先建立即時 fixture；重新貼上第 1 步的 `Write-LabJson` 函式：

```powershell
Set-Location "$MreLab/repos/ss-session-source"
$LiveCase = Get-Content examples/demo.json -Raw | ConvertFrom-Json
$LiveCase.scope.profile_id = 'manual-archive01'
$LiveCase.scope.channel_id = 'manual-channel'
$LiveCase.scope.session_id = 'manual-session01'
$EpochNow = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
for ($CaseIndex = 0; $CaseIndex -lt $LiveCase.inputs.Count; $CaseIndex++) {
  $LiveCase.inputs[$CaseIndex].id = "archive01-$CaseIndex"
  $LiveCase.inputs[$CaseIndex].occurred_at = $EpochNow
}
Write-LabJson "$MreLab/fixtures/rabbit-archive01.json" $LiveCase
uv run --extra rabbitmq ss-session-source publish --fixture "$MreLab/fixtures/rabbit-archive01.json" --state-dir "$MreLab/state/rabbit-archive01/source" --exchange ss.mre.archive01
```

預期 source `published=4, pending=0`；archive `handled=4, rejected=0, ok=true`。sink 在處理四筆後自行結束。用 context-store 查閱 archive 的 DB：

```powershell
Set-Location "$MreLab/repos/ss-context-store"
$QueryNow = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
uv run ss-context-store query --db "$MreLab/state/rabbit-archive01/archive/context.db" --profile-id manual-archive01 --channel-id manual-channel --session-id manual-session01 --as-of $QueryNow --user-id fixture:user-1
```

應看到 4 筆。再以另一個 profile 查詢應為空。Broker ready／unacked 應回到零。

**通過條件：** source 不直接寫 archive DB；archive 不產生回答；事件經真實 broker 傳遞並在 ACK 前完成歸檔。Publisher confirm 與 consumer ACK 是不同證據，詳見 [RabbitMQ 官方說明](https://www.rabbitmq.com/docs/confirms)。

## 10. 第二個跨行程實驗：四個 sink 各自 fanout

使用新 profile `manual-fanout01`、exchange `ss.mre.fanout01`、state 根目錄 `rabbit-fanout01`，不要沿用上一階段 queue。先選做 topology：

```powershell
Set-Location "$MreLab/repos/ss-assembly"
uv run --extra rabbitmq ss-assembly topology --profile-id manual-fanout01 --exchange ss.mre.fanout01
```

開四個終端，各自完成第 8 步環境設定後，切到對應 repo，再執行表格中的一列：

| Repo | 指令 |
| --- | --- |
| ss-archive-sink | `uv run --extra rabbitmq ss-archive-sink consume --exchange ss.mre.fanout01 --profile-id manual-fanout01 --channel-id manual-channel --session-id manual-session01 --state-dir "$MreLab/state/rabbit-fanout01/archive" --limit 4 --idle-timeout 120` |
| ss-platform-sink | `uv run --extra rabbitmq ss-platform-sink consume --exchange ss.mre.fanout01 --profile-id manual-fanout01 --channel-id manual-channel --session-id manual-session01 --state-dir "$MreLab/state/rabbit-fanout01/platform" --limit 1 --idle-timeout 120` |
| ss-speech-sink | `uv run --extra rabbitmq ss-speech-sink consume --exchange ss.mre.fanout01 --profile-id manual-fanout01 --channel-id manual-channel --session-id manual-session01 --state-dir "$MreLab/state/rabbit-fanout01/speech" --limit 1 --idle-timeout 120` |
| ss-surface-sink | `uv run --extra rabbitmq ss-surface-sink consume --exchange ss.mre.fanout01 --profile-id manual-fanout01 --channel-id manual-channel --session-id manual-session01 --state-dir "$MreLab/state/rabbit-fanout01/surface" --limit 4 --idle-timeout 120` |

四個 queue 均有 consumer 後，在第五個終端設定環境與 `Write-LabJson` 函式，**重新取當前時間**，隨即發布：

```powershell
Set-Location "$MreLab/repos/ss-session-source"
$LiveCase = Get-Content examples/demo.json -Raw | ConvertFrom-Json
$LiveCase.scope.profile_id = 'manual-fanout01'
$LiveCase.scope.channel_id = 'manual-channel'
$LiveCase.scope.session_id = 'manual-session01'
$EpochNow = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
for ($CaseIndex = 0; $CaseIndex -lt $LiveCase.inputs.Count; $CaseIndex++) {
  $LiveCase.inputs[$CaseIndex].id = "fanout01-$CaseIndex"
  $LiveCase.inputs[$CaseIndex].occurred_at = $EpochNow
}
Write-LabJson "$MreLab/fixtures/rabbit-fanout01.json" $LiveCase
uv run --extra rabbitmq ss-session-source publish --fixture "$MreLab/fixtures/rabbit-fanout01.json" --state-dir "$MreLab/state/rabbit-fanout01/source" --exchange ss.mre.fanout01
```

| 觀察位置 | 預期 |
| --- | --- |
| source 結果 | published=4、pending=0；publish CLI 不輸出 model_calls |
| archive | handled=4、rejected=0；context.db 有 4 筆 |
| platform | handled=1；platform-out.jsonl 一筆短回答 |
| speech | handled=1；state 下產生一個 WAV 與文字 metadata |
| surface | handled=4；surface.html 有四筆，人工開啟／刷新 |
| broker | 各 queue ready／unacked=0，DLQ 無新增 |

speech 以 `occurred_at + 60 秒` 判斷過期。若等待過久，處理成功卻沒有 WAV 可能是正確捨棄，請記為 expiry 案例，再用**新 id／新 state** 建立新實驗。不要在同一 source state 中改既有事件時間來「救回」它。

**通過條件：** 同一公開回答抵達獨立 queue，每個 sink 有自己的 checkpoint；停止任一 sink 不會阻止其他 sink 處理。檔案送達、音調與 HTML 仍是替身驗收。

## 11. 逐一做故障與恢復實驗

每個案例使用獨立 profile／exchange／state，保持測資與觀察可以對應。先跑正常情境，再一次引入一個故障。

### 11.1 沒有 routing：確認 outbox 留存

1. 建立新 source fixture，使用 `manual-unrouted01` profile 與新的 id。
2. 對沒有任何 queue binding 的新 exchange `ss.mre.unrouted01` 執行 `publish`。應結束碼 2；本機 source.db 的 outbox 保留未確認事件。
3. 啟動相符 archive consumer，使用該 exchange、scope 與 `--limit 4`。
4. 使用**原 fixture／原 source state** 再次 `publish`。預期 4 筆送出、pending=0；先前已快取的輸入不再呼叫模型。模型呼叫數需另做 API instrumentation，publish CLI 不提供此計數。

不能把 mandatory unroutable publish 當成成功。恢復時不需要操作員改 DB 或重新製造回答。

### 11.2 Consumer 離線：確認 durable backlog

1. 用新的完整 topology 建立 queue，但先不啟動其中一個 sink；其他 sink 正常啟動。
2. 發布新 fixture。離線 sink 的 queue 應累積 ready，其他 sink 完成。
3. 啟動離線 sink，確認積壓消化、輸出正確、ready／unacked 歸零。

Confirm 只證明 broker 接受並完成 routing，不證明所有 sink 已完成。不要用 source 的 pending=0 取代下游驗收。

### 11.3 分清 Source 重跑與真正重複投遞

1. 已完成的同 fixture／同 source state 再 `publish`，預期 published=0。這驗 source 快取，沒有測到 sink 的重複接收。
2. 要人工驗 sink dedup：重新啟動相同 sink state／queue，用**另一個全新的 source state 目錄**發布原封不動的同 fixture，使相同 event_id 再進 broker。
3. sink 的 handled 可以增加，但 archive 筆數、platform JSONL、已完成 speech 與 surface 筆數不應增加。source 可能重新呼叫固定模型；不要在此案例切換真實非決定性模型。

以上是人工重送相同 envelope。第 11.5 步提供 manual ACK 與重複處理的輔助證據，但沒有刻意製造「副作用完成、ACK 尚未送出」的 crash window；該中斷情境要另外設計故障注入。只驗 source 重跑不等於驗 at-least-once。

### 11.4 Scope 不符：確認 DLQ 與零副作用

1. 啟動新的 archive consumer，預期 scope 為 `manual-scope01/manual-channel/manual-session01`，`--limit 4`。
2. source fixture 改為不同 profile，新的 source state／id，但刻意發布到同 exchange。
3. 預期 archive `handled=0, rejected=4, ok=false`，context DB 無事件；`<queue>.dlq` 有 4 筆。

此 consumer 的結束碼仍可能為 0，務必看 rejected／ok。Scope rejection 正常進 DLQ，不能當作默默成功。先查問題再另做新實驗，不直接重送 DLQ 到正式 queue。

### 11.5 重跑已提供的真實 broker tests，作為輔助證據

```powershell
Set-Location "$MreLab/repos/ss-assembly"
$env:SS_MRE_TEST_AMQP_URL = $env:SS_AMQP_URL
uv run --extra rabbitmq pytest -m integration -v
Remove-Item Env:SS_MRE_TEST_AMQP_URL
```

這 3 個測試覆蓋 fanout／重複處理／manual ACK、unroutable outbox、異 scope DLQ；測試自建唯一資源並清理自己的 queue／exchange。已有 CI 真實 broker 驗證紀錄，但你仍應記錄這次本機結果，不能當作人工測試已完成。

若採連續 consume（不設 limit），Ctrl+C 的 CLI 可能印出 KeyboardInterrupt 並結束碼 2；這是手動停止。Bounded consume 的 idle timeout 則表示未收到預期數量，應檢查 binding、scope、已快取 source 與期限。

**通過條件：** 失敗可觀察、狀態可解釋、復原不破壞資料所有權；至少做完 unroutable、離線 backlog、重複投遞、scope rejection 四項。

## 12. 再接真實 adapter：一次只換一個

建議順序：真實 LLM → 外部 evidence provider → 實際平台 sender → 真正 TTS／播放裝置 → 真實 STT／畫面輸出。每次保留其餘替身，重跑相同輸入與故障案例，再把下一個 adapter 換入。

目前可直接透過 Python API 使用既有 Ollama 服務：

```python
import asyncio
from ss_contracts.core import Scope
from ss_answer.core import answer
from ss_llm_client.core import OllamaClient

async def main():
    # 換成你已安裝、可用的模型名稱；本指南不自動下載模型。
    client = OllamaClient("http://127.0.0.1:11434", "YOUR_INSTALLED_MODEL", timeout=30)
    result = await answer(
        {"question": "請用一句繁體中文說明這是測試。"},
        Scope("model-profile", "model-channel", "model-session"),
        1001, client, timeout=30,
    )
    print(result.status, result.text)

asyncio.run(main())
```

也可在 `ss-session-source publish` 加上成對的 `--ollama-url`／`--model` 與 `--model-timeout`。先在新 scope／state、`platform=fixture` 下測試；目前下游仍是檔案替身，不會自動連接公開聊天室。

注意：`publish` CLI 目前不注入 fixture evidence provider；真實搜尋需另寫 adapter 並經 API 接入。模型缺證回答與語意正確性必須另外人工評分。Ollama 網路工作在線程內執行，等待期限不等於立即停止該線程，網路 timeout 也須有界。

其他真實 adapter 目前尚未提供完整 CLI。先實作明確接口與 fixture，再驗外部效果；不要在表格填「已完成」。實際 STT 音源依舊必須做精確裝置／route 的離線驗收，RabbitMQ 測試不能代替它。

**通過條件：** 同一契約在替身與真實 adapter 下都成立；外部副作用、延遲、失敗與重試均有人工證據。

## 13. 修改 repo 後，確認組合真的用了你的程式

發布套件固定 Git SHA。單純在 sibling checkout 改檔案，其他 repo 不會自動使用它；人工開發整合需另外建立實驗專案。

例如只替換 `ss-prompt`：先建立新的實驗 uv 專案，加入固定版 `ss-answer`：

```powershell
uv init --bare --python 3.11 "$MreLab/experiments/prompt-change01"
Set-Location "$MreLab/experiments/prompt-change01"
uv python pin 3.11
uv add --raw 'ss-answer @ git+https://github.com/HGPT-StreamSuite/ss-answer.git@88e238aa202bfbed912e78a4b6d2435599c56cd7'
```

再修改該實驗專案的 `pyproject.toml`：

```toml
[tool.uv]
override-dependencies = [
  "ss-prompt @ file:///C:/dev/ss-mre-lab/repos/ss-prompt"
]
```

路徑需與你的工作區一致。接著在該實驗專案：

```powershell
uv add --editable "$MreLab/repos/ss-prompt"
uv run python -c 'import ss_prompt; print(ss_prompt.__file__)'
uv tree
uv run ss-answer demo
```

先確認 `__file__` 指向本機修改過的 `ss-prompt/src`。只做 `uv add --editable` 可能與上游固定的 Git URL 發生衝突；此處 override 明確替換直接與遞迴 requirement，方法見 [uv dependency overrides](https://docs.astral.sh/uv/concepts/resolution/#dependency-overrides)。不要用 `--frozen` 隱藏 resolution failure。

一次換一個 repo，記錄本機 commit／diff、override 與 lockfile，再重跑受影響的獨立驗收與整合階段。回到發布基準時使用另一個乾淨實驗專案。開發用絕對路徑不放進各 repo 的發布相依。

## 14. 每個案例留一份可比較的紀錄

在 `evidence` 建立 Markdown，例如 `fanout01.md`：

```markdown
# 案例：fanout01

- 日期／操作者：
- 階段／要驗證的邊界：
- Repo commit／Python／uv 版本：
- Fixture 路徑與 SHA256：
- Scope／exchange／queue 名稱：
- State 目錄：
- Adapter：FixtureClient／FileSender／ToneFilePlayer 等
- 前置條件：空 state、已綁定 queue、consumer 已就緒等
- 操作與完整 CLI（移除 credentials）：
- 預期結果：事件數、model_calls、效果數、拒絕數
- 實際結果：
- 證據：JSON、stderr、DB 唯讀查詢、HTML／JSONL／WAV、broker 截圖
- 結論：通過／失敗／未執行／尚未實作
- 不確定性與下一步：
```

PowerShell 可用 `Get-FileHash -Algorithm SHA256 <fixture-path>` 保存測資識別。包含真實 prompt／觀眾資料的診斷留在本機，不上傳公開 repo；指南與合成測資可以公開。

最後用下表追蹤，不把未執行欄位算成通過：

| 階段 | 完成標準 | 狀態／證據 |
| --- | --- | --- |
| 單 repo | 12 份職責筆記、各一正常／異常案例 | |
| 手動資料交接 | source events 無修改交給四 sink | |
| 持久離線組合 | 初次效果、重啟去重、collision 可解釋 | |
| uv／API | 固定依賴可裝；context 注入、逾時、checkpoint 恢復 | |
| RabbitMQ 最小組合 | Source → Archive、scope 與 ACK 有證據 | |
| RabbitMQ fanout | 四條獨立 queue／效果／狀態皆確認 | |
| 故障復原 | outbox、backlog、dedup、DLQ 四案例 | |
| 真實 adapter | 每個 adapter 分別記錄；缺少實作標明 | |

建議把每個階段當成一個可獨立收尾的實驗。只有當輸入、輸出、資料擁有者與復原方式都說得清楚，才把下一個 repo 或 adapter 接進來。
