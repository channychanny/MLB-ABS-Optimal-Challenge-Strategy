# MLB ABS Optimal Challenge Strategy

本專案研究在 MLB 2026 每隊僅有兩次 ABS Challenge 的制度下，何時使用 Challenge、何時保留額度，才能最大化球隊的 Expected Win Probability。

**Phase 0 — Data Feasibility Gate（資料可行性閘門）已於 2026-09-12 通過。** 2023–2025 Triple-A 與 2026 MLB 各有 3 場通過單場稽核，且逐球擷取與官方終場 ABS 計數的 comparison 誤差為 0。專案可進入 Phase 1 的 RE／WP baseline prototype；Future Opportunity、Dynamic Policy 與 RRA 尚未完成，不得描述為研究成果。

**2026-09-15：Phase 1 已依使用者同意，以官方 ±5 分覆蓋作限定原型驗收；Phase 2 已開始。** 官方 RE288／含球數 WP snapshot、兩種判決估值及合成 Dynamic 流程已跑通。v2 已修正打方轉主隊的視角錯誤：真實 3 場／16 次挑戰中，12 次可查表、零方向警示，4 次超出範圍仍保留缺值；其中 2 場／10 次完整通過。詳見 [Phase 1 報告](reports/phase1_baseline.md)。Phase 2 已建立 Dataset A 與 Train-only RE 開發命令，**尚未訓練或校準 WP 模型**；見 [Phase 2 工作地圖](.scratch/phase2-models/map.md)。

## 已實作範圍

- 從官方 MLB Stats API live feed 擷取逐球 ABS Challenge。
- 復原翻判前的主審判決，並處理只出現在 plate-appearance result 的終局 Challenge。
- 依比賽日期、聯盟及版本化設定解析 Challenge 規則。
- 重建兩隊 Challenge 額度與成功保留額度；延長賽補充邏輯只保留為資料工程防呆。
- 將 Challenge 與 Baseball Savant 逐球資料以 `game_pk`、`at_bat_number`、`pitch_number` 串接。
- 建立 Legal／Reasonable Challenge Opportunity；不以實際 Challenge Attempt 充當全部 opportunity。
- 將決策前狀態與事後結果欄位分離，降低 data leakage。
- 為下載資料與輸入檔建立 URL、參數、時間、SHA-256、列數等 provenance manifest。
- 依 `config/phase0_gate.json` 彙總跨年度樣本並判定 Phase 0。

目前可重現的實例與尚未完成項目記錄於 [Phase 0 可行性報告](reports/phase0_feasibility.md)，欄位定義見 [資料字典](docs/data_dictionary.md)，評估與防洩漏規則見 [評估設計](docs/evaluation_design.md)。

## 本機執行

本階段只使用 Python standard library。

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

### 下載與稽核單場 Challenge

`audit-game` 會自動從 `config/rule_regimes.json` 解析規則。2023 或 2024-06-25 前的 feed 若實際包含 `reviewType=MJ`，該場可直接確認為 Challenge System；沒有事件證據時，即使明確傳入 `--abs-format challenge`，狀態仍維持 provisional，不會因人工參數自行升級為已確認。

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.cli download-statcast-abs --date 2026-03-28 --level mlb --output data/raw/savant_mlb_2026-03-28_abs.csv
python -m abs_challenge.cli audit-game --game-pk 823488 --raw-output data/raw/game_823488.json --savant-csv data/raw/savant_mlb_2026-03-28_abs.csv --output data/processed/audit_823488.json
```

下載指令會在輸出旁建立 `<檔名>.manifest.json`。單場稽核只有在 Challenge、Savant join、必要狀態、規則 regime、decision side、挑戰資格，以及可用時的官方終場 ABS counter 全部通過時回傳 exit code `0`；未完成或失敗時回傳 `1`，規則無法解析時回傳 `2`。守方無法再區分 pitcher／catcher 只列為資料品質指標，不阻擋 team-level Gate。

### 建立 Challenge Opportunity 資料集

Legal Opportunity 需要完整逐球資料，不能使用只含實際 Challenge 的 CSV。

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.cli download-statcast-pitches --date 2026-03-28 --level mlb --output data/raw/savant_mlb_2026-03-28_pitches.csv
python -m abs_challenge.cli build-opportunities --feed-json data/raw/game_823488.json --statcast-csv data/raw/savant_mlb_2026-03-28_pitches.csv --output data/processed/opportunities_823488.json
```

輸出內的 `model_input_contract` 是強制防洩漏契約：正式模型只能使用 `pre_pitch_state`、`challenges_remaining`、`original_call` 與 `decision_team_id` 等決策當下已知資訊。`actual_challenge`、`overturned`、`reasonable_candidate`、`pitch_observation` 與 `delta_*` 只能作標籤或事後分析。

Opportunity dataset 預設且固定只輸出第 1–9 局。第 10 局以後的 Challenge strategy 不屬於本次研究範圍；既有延長賽 audit 與 ledger 支援只是 regression protection。

### 彙總 Phase 0

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.cli build-official-comparison --scope-id regulation-sample-2023-2026 --audit data/processed/audit_723845.json --audit data/processed/audit_723507.json --audit data/processed/audit_721393.json --audit data/processed/audit_753349.json --audit data/processed/audit_753200.json --audit data/processed/audit_751852.json --audit data/processed/audit_779936.json --audit data/processed/audit_780910.json --audit data/processed/audit_780009.json --audit data/processed/audit_823244.json --audit data/processed/audit_823569.json --audit data/processed/audit_825027.json --feed-json data/raw/game_723845.json --feed-json data/raw/game_723507.json --feed-json data/raw/game_721393.json --feed-json data/raw/game_753349.json --feed-json data/raw/game_753200.json --feed-json data/raw/game_751852.json --feed-json data/raw/game_779936.json --feed-json data/raw/game_780910.json --feed-json data/raw/game_780009.json --feed-json data/raw/game_823244.json --feed-json data/raw/game_823569.json --feed-json data/raw/game_825027.json --output data/processed/official_comparison_regulation_sample.json
```

再將同一組 12 份 `audit_*.json`、`config/phase0_gate.json` 與上述 comparison 傳入 `validate-phase0`。目前可重現結果為 `phase0_gate_pass = true`，61 次 attempts 與 30 次 overturned 均和官方 counter 完全一致。`build-official-comparison` 以官方 live feed 的 `gameData.absChallenges.usedSuccessful/usedFailed` 為獨立終場計數；`validate-phase0` 會依 requirements 重新計算誤差，不信任輸入檔既有的 `pass`。

## 關鍵 feed 語意

Challenge 翻判成功時，live feed 的 `details.call` 儲存 ABS 修正後判決，`reviewDetails.isOverturned` 為 `true`。因此原始主審判決是儲存判決的相反結果；若直接把儲存值當成原判，會顛倒挑戰方並破壞 counterfactual state。

## Phase 1：官方 Baseline 原型

新命令預設拒絕覆寫既有檔案；重跑時請使用新輸出檔名。下載需要網路，其餘命令可離線執行。

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m abs_challenge.cli download-baseline --raw-output data/raw/savant_baseline_new.json --output data/processed/savant_baseline_new.json
```

本輪重播使用已保存的 2026-09-14 原始 bundle，轉換成修正後 v2（不是重新下載）：

```powershell
python -m abs_challenge.cli build-baseline --bundle data/raw/savant_baseline_2026-09-14.json --output data/processed/savant_baseline_v2_2026-09-15.json
python -m abs_challenge.cli value-challenges --baseline data/processed/savant_baseline_v2_2026-09-15.json --phase0-gate data/processed/phase0_gate_current.json --audit data/processed/audit_823244.json --audit data/processed/audit_823569.json --audit data/processed/audit_825027.json --feed-json data/raw/game_823244.json --feed-json data/raw/game_823569.json --feed-json data/raw/game_825027.json --output data/processed/phase1_values_v2_2026-09-15.json
python -m abs_challenge.cli run-dynamic-prototype --baseline data/processed/savant_baseline_v2_2026-09-15.json --output data/processed/phase1_dynamic_v2_2026-09-15.json
```

`value-challenges` 回傳 `0` 表示小樣本全部可估值且無方向警示，`1` 表示已寫出部分結果／品質警示，`2` 表示輸入、來源指紋或 Gate 無效。上述真實樣本目前預期回傳 `1`，不可當作完整通過。其他 Phase 1 命令成功為 `0`、失敗為 `2`。

新 clone 不含本機資料；必須取得原始 snapshot／feed／audit，並重建本機 Phase 0 Gate（其中來源路徑為絕對路徑）。重新下載可重跑方法，但外部服務可能更新，不能保證與舊快照逐 byte 相同；真正重播要使用同一原始 bundle。

舊 `savant-baseline-v1` 把原始打方值誤讀為主隊值，已停用；不能再使用舊的 `phase1_values_current.json` 或 v1 衍生報告。詳細轉換決策見 [ADR-0001](docs/adr/0001-savant-probability-perspective.md)。

此階段不訓練模型，官方頁面資料年份 2016–2025 不等於自建 WP 的 Train／Validation／Test 分工。合成 Dynamic 情境不使用實際比賽未來路徑，不代表已求得正式最佳策略。欄位與假設見 [Phase 1 契約](docs/phase1_baseline.md)。

## 研究邊界

- 最終主要制度固定為 MLB 2026 兩次 Challenge；歷史三次制度只供行為與敏感度分析。
- 正式 Opportunity、RRA 與 Policy 結果只涵蓋第 1–9 局；延長賽留待 MVP 完成後擴充。
- 九局平手以明確揭露的 Regulation Boundary Value 承接，不模擬延長賽 Challenge policy。
- Full ABS 比賽一律排除。
- Phase 0 已通過，Phase 1 已限定驗收，現進入 Phase 2；Legal Opportunity 的 technical outage 與 post-replay-review 排除仍是正式 policy 建模前的已知缺口。
- `.gitignore` 排除本機下載與衍生資料；重現結果時必須重新下載或取得對應 snapshot 與 manifest。

## Phase 2：自建資料與 RE 開發流程

目前仍只需 Python standard library。下載命令保存單場官方 feed 與比賽日完整 MLB CSV；資料建置會核對官方投球總數、完整逐球鍵及逐局／終場比分。所有新命令拒絕覆寫。

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m abs_challenge.cli download-historical-game --game-pk 564960 --output data/raw/historical_564960_new.json
python -m abs_challenge.cli build-historical-dataset --bundle data/raw/historical_564960_new.json --output data/processed/dataset_a_564960_new.json
python -m abs_challenge.cli estimate-re-development --dataset data/processed/dataset_a_564960_new.json --output data/processed/re_564960_new.json
```

以上是小樣本開發流程，不是全季訓練命令。真實 2019 年樣本已通過 283 球核對，包含 34 球絕對分差大於 5 的狀態；沒有截尾。RE24／RE288 的未觀測格保留 null，不代表已有完整 league-average RE。資料契約、排除條件及後續 WP 計畫見 [Phase 2 說明](docs/phase2_dataset.md)，目前驗證紀錄見 [Phase 2 報告](reports/phase2_progress.md)。

**2026-09-16：批次快取與跨年度驗證已完成第一輪。** 五個年度、十日、20 場中，15 場／4,303 球通過，另 5 場因敬遠／計時器非投球事件與編號差異先排除。離線續跑零下載、20 個分片重用、開發 lock 一致。此結果不代表全季資料或 WP 已完成。操作見 [批次下載說明](docs/phase2_batch.md)，證據與待處理問題見 [跨年度批次報告](reports/phase2_batch_validation.md)。該次驗證執行時尚無專案 commit，仍屬開發結果。

## Git 版本紀錄

2026-09-16 依使用者授權，接續 [GitHub 儲存庫](https://github.com/channychanny/MLB-ABS-Optimal-Challenge-Strategy) 的既有 `main` 歷史，保存目前程式、測試、文件、專案技能與 Markdown Issue。原始資料、衍生資料及巢狀快取留在本機，不納入提交。正式實驗必須記錄實際執行時的 commit SHA 與工作目錄狀態；建立 Git 基準不代表既有開發資料已升格為正式訓練集。
