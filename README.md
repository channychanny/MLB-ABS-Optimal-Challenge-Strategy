# MLB ABS Optimal Challenge Strategy

本專案研究在 MLB 2026 每隊僅有兩次 ABS Challenge 的制度下，何時使用 Challenge、何時保留額度，才能最大化球隊的 Expected Win Probability。

**2026-10-01 主線範圍更新：**不再開發未來「值得挑戰」機會的機率／期望值模型。歷史不利判決不等於值得挑戰；未挑戰球缺乏可靠翻判標籤與球員當時把握，直接當成未來可用機會會高估保留額度。現行成果聚焦**眼前已可挑戰情境**的官方 S0／S1 WP、輔助 RE 與明示假設額度成本下的條件式門檻；不宣稱已求得真實額度價值、最優策略或正式 RRA。既有未來模型與稽核保留為歷史探索，不接入即時建議。見[範圍決議](reports/archive/phase3/phase3_scope_decision_2026-10-01.md)。以下先前進度按執行當時語境閱讀。

研究進度建議依序閱讀四份主要入口：[Phase 0](reports/phase0_feasibility.md)、[Phase 1](reports/phase1_integrated.md)、[Phase 2](reports/phase2_integrated.md)與[Phase 3](reports/phase3_integrated.md)。歷史逐輪報告封存於 `reports/archive/`，保留當時數字、修正與來源證據；Phase 2 整合報告末節的舊 Phase 3 計畫已由現行範圍決議取代。

資料夾用途：`reports/` 頂層是四份主要報告，`reports/archive/` 是可追溯的逐輪證據；`docs/` 保存資料／評估契約而非進度報告，`.scratch/` 是 Markdown Issue tracker；`config/` 為版本化規則與實驗設定，`src/`、`scripts/`、`tests/` 分別為程式、入口與測試。`data/raw/` 和 `data/processed/` 是本機來源／衍生資料，受 `.gitignore` 排除，**不因報告封存而清除**。

**Phase 0 — Data Feasibility Gate（資料可行性閘門）已於 2026-09-12 通過。** 2023–2025 Triple-A 與 2026 MLB 各有 3 場通過單場稽核，且逐球擷取與官方終場 ABS 計數的 comparison 誤差為 0。專案可進入 Phase 1 的 RE／WP baseline prototype；Future Opportunity、Dynamic Policy 與 RRA 尚未完成，不得描述為研究成果。

**2026-09-15：Phase 1 已依使用者同意，以官方 ±5 分覆蓋作限定原型驗收；Phase 2 已開始。** 官方 RE288／含球數 WP snapshot、兩種判決估值及合成 Dynamic 流程已跑通。v2 已修正打方轉主隊的視角錯誤：真實 3 場／16 次挑戰中，12 次可查表、零方向警示，4 次超出範圍仍保留缺值；其中 2 場／10 次完整通過。詳見 [Phase 1 報告](reports/archive/phase1/phase1_baseline.md)。Phase 2 已建立 Dataset A 與 Train-only RE 開發命令，**尚未訓練或校準 WP 模型**；見 [Phase 2 工作地圖](.scratch/phase2-models/map.md)。

## 目前主線（2026-09-21）

2026-09-21 決策：主要研究改用固定官方 WP／RE288，自建 WP 與全季 Dataset A 擴充改列延伸研究並暫緩。既有成果與資料契約保留；不截尾真實分差，不宣稱正式 Dynamic Policy／RRA 已完成。

上方日期段落記錄歷史進度；目前執行順序以 [官方 WP 主線契約](docs/official_wp_policy.md) 與 [新工作地圖](.scratch/official-wp-policy/map.md) 為準。2026-09-24 固定跨年度 cohort 的 18 場兩次制樣本均完成暫定機會事件對齊；2,218／2,489 個有額度候選（89.11%）可同時查 S0／S1 WP，並已輸出分組支持與逐筆缺值原因。780464 的 `AB` 非投球自動好球已嚴格對齊，先前 17 場結果不變。另有[合成有限樹契約](reports/archive/phase2/official_wp_continuation_contract.md)驗證表外回表及未知區間，但不估計真實未來機率。24 場來源訊號已盤點，ABS unavailable／replay 逐球資格仍未知；[Dataset B 時間窗與已知開發場排除規則](reports/archive/phase2/dataset_b_readiness_2026-09-24.md)已預宣告，並已從[官方賽程鎖定 96 場候選](reports/archive/phase2/dataset_b_schedule_lock_2026-09-24.md)。候選仍待逐場制度與資格確認，不能稱正式 holdout、Legal Opportunity 或 Phase 3 策略完成。

2026-09-24 的 Dataset B 訓練前來源準備結果：96 場官方 feed 均取得，85 場通過完整逐球對齊並輸出 13,252 個暫定候選與觀察性到達間隔／右設限；當時 11 場官方計數不符保留失敗，不補樣。ABS 停用與 replay 來源資格仍未知，`training_ready=false`。見[當時的訓練前準備報告](reports/archive/phase2/dataset_b_pretraining_preparation_2026-09-24.md)。

2026-09-29 更新：11 場不符中 6 場經 ABS-only／完整逐球／官方分隊計數嚴格復原，5 場無法定位而整場排除，固定選場不替補。91 場形成 13,132 筆有額度暫定風險集候選；到達標籤已排除零額度與位置球員投手候選，並通過[限定模型輸入閘門](reports/archive/phase2/dataset_b_challenge_recovery_2026-09-29.md)。

2026-09-29 基線進度：已依 Train／Validation／Test／External 切分完成第一個帶右設限 likelihood 的離散到達 hazard 基線；Validation 選出依球數和剩餘額度分層模型。Test 的對數損失略有改善，但 2026 External 的遊戲層級區間仍涵蓋無改善；各預測視野的 Brier 分數也沒有一致勝出。這只描述歷史實際路徑下的候選到達，不是挑戰行動的反事實或正式策略；詳見[基線評估報告](reports/archive/phase2/dataset_b_observational_baseline_2026-09-29.md)。完整 Legal Opportunity、正式策略與 RRA 仍未完成。

同日後續[行動支持與設限稽核](reports/archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md)發現：182 筆原列「九局設限」的 episode 至少 45 筆實為額度耗盡後仍有零額度候選，另 6 筆當時無法由候選檔判定；舊 hazard／NLL／Brier 不可作已校正到達模型或策略輸入。Train 的 12 個粗粒度行動支持格只有 2 格通過最低門檻；不能把歷史挑戰／保留差異稱為因果效果。

同日已完成[額度感知新版契約與條件基線](reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md)：以已快取官方 feed 核對原先候選序列無法判定的 6 次最後挑戰，確定 50 筆當下額度耗盡、132 筆額度仍在的九局設限；不將耗盡後投球計入等待曝光。Train／Validation／Test／名義 External 已重新評估**行動及結果已發生後**的條件到達模型。`post_action_budget` 是事後欄位，不能直接作決策時策略輸入；正式反事實與 Dynamic Policy 仍未完成。

同階段延伸已一次完成[缺漏／設限敏感度與下一機會分布](reports/archive/phase2/dataset_b_followup_sensitivity_2026-09-29.md)：固定五場 Train 排除的假設性情境、九局設限分組，以及下一機會的 Decision Side 與官方 WP 價值類別基線。下一方向的條件分布在 Test／名義 External 有明顯 log loss 改善，價值類別在 External 仍無穩定改善證據；價值無法查表的機會獨立保留。歷史行動依賴轉移與完整下一 Game State 分布尚未完成。

2026-09-30 新增[決策時情境原型](reports/archive/phase3/policy_scenario_prototype_2026-09-30.md)：可輸入單一 Game State，或重播固定 91 場／13,132 筆暫定機會，在明示的人工翻判成功率及未來額度成本下比較「挑戰／保留」。11,060 筆兩側 WP 可估；其餘 2,072 筆明列不支援。Test 的 1,579 筆可估機會中，假設成功率 0.50 時，小成本與大成本情境分別有 1,382 與 643 筆建議挑戰，顯示結論對未經估計的假設敏感。這不是實證最適策略、正式 RRA 或樣本外政策績效；技術可用性、未來反事實及表外 continuation 仍待解決。

2026-10-01 完成[修訂後 Phase 2 限定收尾驗收](reports/archive/phase2/official_wp_phase2_closeout_2026-10-01.md)：固定 96 場中 91 場納入、5 場嚴格排除；7 場來源比賽雖進入延長賽，13,132 筆主候選全在第 1–9 局。13,132 筆的 ABS technical outage／replay 後資格仍全部未知。九局平手直接終局的人工邊界壓力測試只碰到 1 筆候選，且其情境建議可翻轉，不能稱全政策穩健。**可進入明示假設的 Phase 3 策略原型，但完整 Legal Opportunity、反事實轉移及正式 Policy Gate 仍未通過。**

2026-10-01 已完成[Phase 3 第一輪九局假設式動態模型](reports/archive/phase3/phase3_synthetic_regulation_policy_2026-10-01.md)：明示每局人工未來機會、WP 損失及翻判率，倒推 `V(S,0/1/2)`，比較永不挑戰、固定信心門檻及動態原型，並以固定 91 場盤點合成門檻與情境翻轉。Test 的 1,579 筆可估候選在 `p=0.50` 下，三組人工未來情境分別有 1,521／1,095／772 筆建議挑戰；這是模型內部建議，不是實證增勝或正式 RRA。Phase 3 尚未完成反事實 Game State／表外 continuation 與正式政策評估。

**Phase 3 現行主線是[挑戰隊伍勝率決策分析](reports/archive/phase3/phase3_win_decision_primary_2026-10-01.md)**：給定已可挑戰的 Game State、官方 `WP(S0)`／`WP(S1)`、主觀翻判率及明示的失敗額度成本，輸出立即預期勝率增益、可承受成本上限與條件式建議。Test 的 1,579 筆可估候選在 `p=0.50` 時，立即預期增益中位數為 0.45 個百分點；小／大人工成本下分別有 1,382／643 筆建議挑戰。合成未來模型只保留作次要敏感度檢查，不作本研究主結論；ABS 故障是候選母體限制，不是已可挑戰情境的決策公式閘門。

**可直接使用瀏覽器介面：**在專案根目錄執行 `python scripts/start_abs_ui.py`，開啟 `http://127.0.0.1:8765/`，填入投球前比賽狀態、主審原判與該隊剩餘額度。介面先並列原判／翻判的官方 WP 與 RE288；RE 為原半局打方的預期得分，另轉成挑戰方視角顯示得分變化。WP 表外時仍可顯示 RE，但不計算 WP 門檻。下方只列事先宣告的零／低／高**假設額度成本**及對應門檻範圍；這不是估計出的真實成本、信賴區間或最優建議。使用者不需先猜眼前翻判率，可在進階設定自行假設成本。RE 不與 WP 相加。舊[兩機會近似](reports/archive/phase3/phase3_option_value_and_ui_2026-10-01.md)保留研究紀錄但不再接入即時介面；下一版研究見[額度價值重新設計](reports/archive/phase3/phase3_option_value_redesign_plan_2026-10-01.md)及[第一輪事前資訊稽核](reports/archive/phase3/phase3_decision_time_feasibility_2026-10-01.md)。服務只綁定本機。

同日新增[Phase 3 歷史路徑與表外支持稽核](reports/archive/phase3/phase3_empirical_path_support_2026-10-01.md)：固定 91 場／13,132 筆候選一對一核對額度感知後續；1,063 個表內起點在後續同隊候選中曾表外又返回，證明不能忽略跨界路徑。此數是重疊的歷史路徑起點，不是反事實跨界機率；ABS 停用／replay 資格仍未知、歷史挑戰稀少，正式 Legal／Policy Gate 仍未通過。

## 已實作範圍

**2026-09-22：固定六場完整逐球覆蓋完成。** 五球出局數差異確認為終局三振 count 延遲，actual attempts 修正為 22／29。1,876 球對齊通過；962 個暫定機會中 706 個兩側可估值，80 個零額度候選另外保留。214 項測試通過、離線重播一致；仍非完整法律資格或全季驗收，見 [最新報告](reports/archive/phase2/official_wp_opportunity_coverage.md)。

**2026-09-21：官方 WP 覆蓋檢查第一輪。** 固定六場開發樣本，29 次 regulation attempts 中 17 次兩側可估值、7 次兩側超界、5 次純判決出局數不符；208 項測試通過、離線重播一致。這不是全部機會覆蓋率，Issue 01 尚未完成。見 [覆蓋報告與命令](reports/archive/phase2/official_wp_coverage_development.md)。

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
- Phase 0 已通過，Phase 1 已限定驗收，目前主線為官方 WP 覆蓋與策略資料準備；Legal Opportunity 的 technical outage 與 post-replay-review 排除仍是正式 policy 建模前的已知缺口。
- `.gitignore` 排除本機下載與衍生資料；重現結果時必須重新下載或取得對應 snapshot 與 manifest。

## Phase 2：保留的自建資料與 RE 開發成果（延伸研究）

目前仍只需 Python standard library。下載命令保存單場官方 feed 與比賽日完整 MLB CSV；資料建置會核對官方投球總數、完整逐球鍵及逐局／終場比分。所有新命令拒絕覆寫。

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m abs_challenge.cli download-historical-game --game-pk 564960 --output data/raw/historical_564960_new.json
python -m abs_challenge.cli build-historical-dataset --bundle data/raw/historical_564960_new.json --output data/processed/dataset_a_564960_new.json
python -m abs_challenge.cli estimate-re-development --dataset data/processed/dataset_a_564960_new.json --output data/processed/re_564960_new.json
```

以上是小樣本開發流程，不是全季訓練命令。真實 2019 年樣本已通過 283 球核對，包含 34 球絕對分差大於 5 的狀態；沒有截尾。RE24／RE288 的未觀測格保留 null，不代表已有完整 league-average RE。資料契約、排除條件及後續 WP 計畫見 [Phase 2 說明](docs/phase2_dataset.md)，目前驗證紀錄見 [Phase 2 報告](reports/archive/phase2/phase2_progress.md)。

**2026-09-16：批次快取與跨年度驗證已完成第一輪。** 五個年度、十日、20 場中，15 場／4,303 球通過，另 5 場因敬遠／計時器非投球事件與編號差異先排除。離線續跑零下載、20 個分片重用、開發 lock 一致。此結果不代表全季資料或 WP 已完成。操作見 [批次下載說明](docs/phase2_batch.md)，證據與待處理問題見 [跨年度批次報告](reports/archive/phase2/phase2_batch_validation.md)。該次驗證執行時尚無專案 commit，仍屬開發結果。

**2026-09-18：Phase 2 Issue 06 已完成固定樣本驗證。** Dataset A v2 以事件、判決、球數與跑者狀態處理非投球及編號偏移。同一 20 場全數通過，共 5,748 球；10 筆非投球只留作對齊證據，14 球保留不同來源編號。原先 15 場資料內容不變，179 項測試通過。這不是全季或 WP 模型完成；下一步為 Issue 03 的覆蓋與排除率驗證。詳見 [對齊驗證報告](reports/archive/phase2/phase2_alignment_validation.md)。

**2026-09-18：跨月份擴大工程抽樣完成。** 五年度 4–9 月的固定計畫實際選定 84 場，70 場／20,234 球通過，14 場來源差異保留排除；已有 2 場真實再見與 8 場 Train 九局平手。離線重播零下載且 lock 一致，185 項測試通過。新缺口追蹤於 Issue 07；全季、正式資料版本與 WP 訓練尚未完成。詳見 [擴大覆蓋報告](reports/archive/phase2/phase2_expanded_coverage.md)。

**2026-09-19：Issue 07 修正完成。** 同一固定 84 場全數通過，共 24,448 球；原 70 場完整資料指紋不變。補齊 pitchout／missed_bunt，N 型非投球保留跑壘證據、不產生投球樣本。192 項測試通過，離線重播 lock 一致。正式全季與 WP 訓練仍未完成，詳見 [最新驗證報告](reports/archive/phase2/phase2_issue07_validation.md)。

**2026-09-19：全季取得已開始。** 固定五年度 12,029 場／36 月計畫，2019 年 3 月全部 54 場／15,627 球通過，離線重播一致，199 項測試通過。未壓縮全季容量高於目前保留空間後的預算，後續先處理 Issue 08 壓縮儲存；全季資料與正式版本尚未完成。見 [首月報告](reports/archive/phase2/phase2_season_acquisition.md)與[執行方式](docs/phase2_season_acquisition.md)。

## Git 版本紀錄

2026-09-16 依使用者授權，接續 [GitHub 儲存庫](https://github.com/channychanny/MLB-ABS-Optimal-Challenge-Strategy) 的既有 `main` 歷史，保存目前程式、測試、文件、專案技能與 Markdown Issue。原始資料、衍生資料及巢狀快取留在本機，不納入提交。正式實驗必須記錄實際執行時的 commit SHA 與工作目錄狀態；建立 Git 基準不代表既有開發資料已升格為正式訓練集。
