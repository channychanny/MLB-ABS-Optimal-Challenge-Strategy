# Phase 0 資料可行性報告

狀態：**已通過 Phase 0**  
更新日期：2026-09-12

## 結論

`validate-phase0` 已對 12 場 regulation-only 跨年度樣本回傳 `phase0_gate_pass = true`：2023、2024、2025 Triple-A 與 2026 MLB 各 3 場，所有單場 audit 均通過，沒有重複 `game_pk`。逐球擷取與官方 live feed 終場 ABS 計數的 attempts 為 61／61、overturned 為 30／30，兩項誤差皆為 0。

這代表 Challenge 擷取、Savant join、規則解析、team-level eligibility 與 ledger 重建已達到最低資料可行性門檻，可進入 Phase 1 RE／WP baseline prototype。每年度 3 場只是 smoke test，不代表完整歷史資料已具統計代表性，也不表示 Future Opportunity、Dynamic Policy 或 RRA 已完成。

## Gate 結果

| 項目 | 結果 |
|---|---:|
| 稽核場次 | 12 |
| 2023 Triple-A | 3／3 |
| 2024 Triple-A | 3／3 |
| 2025 Triple-A | 3／3 |
| 2026 MLB | 3／3 |
| 單場失敗 | 0 |
| 重複 `game_pk` | 0 |
| 官方 comparison attempts | 61 observed／61 official |
| 官方 comparison overturned | 30 observed／30 official |
| `phase0_gate_pass` | `true` |

Gate 設定來自 `config/phase0_gate.json`；本機結果寫入 `data/processed/phase0_gate_current.json`。原始與衍生資料受 `.gitignore` 排除，重現時需重新下載或取得相同 snapshot 與 companion manifests。

## 已實作

- 官方 MLB Stats API live-feed client。
- pitch-level ABS review 擷取。
- plate-appearance result 才有記錄的 terminal Challenge fallback。
- 翻判成功後原始主審判決復原。
- 依版本化 rule regime 自動解析初始額度與成功保留規則；延長賽狀態獨立記錄。
- Baseball Savant ABS／完整逐球 CSV 下載與三欄唯一鍵 join。
- pre-pitch state 必要欄位、count 一致性、重複 key 與零事件檢查。
- Legal／Reasonable Opportunity 原型，包含實際未挑戰的 adverse called pitches。
- position player pitching 的 Legal Opportunity 排除。
- 決策前 feature 與事後 observation／label namespace 分離。
- 下載與輸入檔 provenance manifest。
- 跨年度 Phase 0 gate 與官方 aggregate 誤差重算。

## 跨年度樣本

| 年度 | 賽事 | 聯盟 | Challenge | Overturned | 延長賽 | Audit |
|---:|---:|---|---:|---:|---|---|
| 2023 | 723845 | International League | 7 | 6 | 否 | pass |
| 2023 | 723507 | International League | 8 | 3 | 否 | pass |
| 2023 | 721393 | Pacific Coast League | 4 | 1 | 否 | pass |
| 2024 | 753349 | International League | 4 | 1 | 否 | pass |
| 2024 | 753200 | International League | 4 | 2 | 否 | pass |
| 2024 | 751852 | Pacific Coast League | 5 | 2 | 否 | pass |
| 2025 | 779936 | Pacific Coast League | 5 | 2 | 否 | pass |
| 2025 | 780910 | International League | 5 | 2 | 否 | pass |
| 2025 | 780009 | Pacific Coast League | 3 | 1 | 否 | pass |
| 2026 | 823244 | American League | 1 | 0 | 否 | pass |
| 2026 | 823569 | National League | 9 | 7 | 否 | pass |
| 2026 | 825027 | American League | 6 | 3 | 否 | pass |

延長賽場次可用來確認 parser 與 ledger 不會失效，但主要 Opportunity dataset 固定只輸出第 1–9 局。第 10 局以後的 Challenge refill、arrival 與最佳策略不屬於本次研究。可攜式延長賽官方摘要 fixture 位於 `tests/fixtures/official_game_823488_excerpt.json`。

稽核期間另發現部分候選場次的逐球事件比官方終場 counter 少 1 次。這些場次會由新增的 `official_counter_pass` 直接判為失敗，並未納入上表或最終 Gate；它們仍可留作後續研究歷史 feed 缺漏模式的診斷樣本。

## 歷史資料發現

### 2023

Baseball Savant 的 `hfABSFlag` 查詢在 2023-07-15 回傳 0 列，但同日完整 Triple-A pitch CSV 有 4,689 列，且三場樣本的官方 live feed 均有 `reviewType=MJ` 的 ABS review 事件。這些事件只確認被抽中場次是 Challenge System，不推論同日或全年所有比賽的 format。

### 2024

`hfABSFlag` 在 2024-07-06 同樣回傳 0 列；完整 Triple-A pitch CSV 有 4,436 列，並可與三場 live feed 的全部 Challenge 精確連接。樣本同時涵蓋 2024-06-25 後的 International League 兩次額度與 Pacific Coast League 三次額度 regime。

### 2025 與 2026

Savant ABS 篩選可直接使用。2025-05-10 Triple-A 回傳 49 列，2026-04-04 MLB 回傳 62 列；抽樣場次的三欄 join、count、比分、壘包與出局數均完整。

## 官方終場計數核對

comparison scope 為上表全部 12 場。程式將 audit 的逐球 `challenge_events`／`overturned` 加總，對照官方 Stats API `gameData.absChallenges` 的 `usedSuccessful`／`usedFailed`：

- observed attempts：61；official attempts：61。
- observed overturned：30；official successful：30。
- attempt relative error：0。
- overturn-rate absolute error：0。

`build-official-comparison` 會驗證 audit 與 feed 的 `game_pk` 集合完全相同、拒絕重複場次或缺少官方 counter 的 feed，並為所有輸入保存 SHA-256 manifest。

## 重要研究發現

1. 翻判事件的 live feed 儲存修正後 ABS call，原判必須取相反值。
2. 只讀 pitch-level `reviewDetails` 會把 game 779936 少算 40%（3 次而非 5 次）。
3. 單靠已擷取事件彼此自洽仍可能漏事件；每場必須與 `gameData.absChallenges` 終場計數一致，否則 `phase0_game_pass = false`。
4. 歷史 `hfABSFlag` 回傳 0 不代表沒有 Challenge；2023／2024 必須以完整逐球 CSV 搭配 live feed 事件驗證。
5. 實際 Challenge Attempt 受到既有策略與剩餘額度影響，不能當成全部 Future Opportunity；完整逐球 Legal population 已另建。
6. 2025 Triple-A 缺少 player 身分時，仍可做 team-level ledger 與使用時機研究；pitcher／catcher 細分只能在 exact role attribution 完整的子樣本進行。
7. `delta_run_exp`、`delta_home_win_exp`、精確 ABS 球位與翻判結果屬事後資料，不得作 decision-time predictor。

## 版本化 Gate

`config/phase0_gate.json` 目前要求：

- 2023 Triple-A、2024 Triple-A、2025 Triple-A、2026 MLB 各至少 3 場。
- 所有納入場次的單場 audit 通過。
- 不得有重複 `game_pk`。
- 至少一份官方 aggregate comparison，attempt 相對誤差不超過 1%，overturn rate 絕對誤差不超過 1 個百分點。

每年度三場只是最低 smoke-test 門檻，不代表統計代表性。實際抽樣仍需跨聯盟、日期、額度制度、翻判結果、terminal fallback 及守方／打方 Challenge。延長賽不是 Gate 必要條件。

## 仍未完成與下一階段限制

- 每年度三場只驗證管線，不足以支撐最終統計推論；正式 Historical Behavior 分析需擴大日期、聯盟、判決方向與 fallback 類型覆蓋。
- player-role 缺失率與 position-player-pitching metadata 覆蓋仍需在完整資料集量化。
- ABS technical outage 與 post-replay-review 尚無可靠逐球排除旗標；`legal_opportunity_criteria.status` 必須維持 `provisional_source_limitations`。
- 2026 資料仍會更新；正式外部驗證必須鎖定 retrieval time、snapshot 與 manifest。
- 目前工作目錄沒有可用的專案 commit SHA；正式模型實驗前需建立可追溯的版本基準，但不得因此重建或覆寫既有專案。

下一個實作階段是 Phase 1：先建立 regulation-inning RE／WP baseline、鎖定時間切分與九局平手的 Regulation Boundary Value，再處理 Future Opportunity 與 Dynamic Policy。延長賽策略保留為 MVP 完成後的 extension。

## 延長賽範圍決策

主要 Opportunity dataset、RRA、Policy Evaluation 與 Dynamic Model 只涵蓋第 1–9 局。九局平手使用版本化 Regulation Boundary Value；不在本次研究中模擬第 10 局以後的 Challenge refill、Opportunity arrival 或最佳使用策略。完整延長賽模型待 regulation-inning MVP 完成後再擴充。
