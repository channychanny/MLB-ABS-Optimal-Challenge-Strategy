# 評估設計與 Data Leakage 防線

## 決策時間點

模型模擬的時間點是：主審已宣告 ball／strike，但球員尚未決定是否 Challenge。所有 predictor 必須在此刻已知，或能由此刻以前的資料重建。

Opportunity dataset 以 `model_input_contract` 固定欄位用途：

- 可用 feature group：`pre_pitch_state`、`challenges_remaining`、`original_call`、`decision_team_id`。
- 只可作 label／事後分析：`actual_challenge`、`overturned`、`reasonable_candidate`、`reasonable_reasons`、`pitch_observation`。

精確 `plate_x`／`plate_z`、`delta_run_exp`、`delta_home_win_exp` 與 ABS 結果都不得直接成為 decision-time predictor。Reasonable Candidate v1 使用其中部分欄位，只是 opportunity label heuristic，不是部署時可見特徵。

## Player Feature 截止時間

rolling wOBA、xwOBA、K%、BB%、投打慣用手、on-deck strength 等 player context 必須以該場比賽開打前為截止點。任何同場或未來比賽資料都不得回填至該場 feature。

建議每筆衍生 player feature 保存：

- `as_of_date`
- 計算窗口與最小樣本數
- source snapshot hash
- 缺失與新人 fallback 規則

## 資料集分工

- Dataset A（MLB historical）：保留供延伸研究訓練 RE／WP 與一般狀態轉移；全季取得與自建 WP 暫緩。主要估值使用固定官方快照，見 [官方 WP 主線](official_wp_policy.md)。
- Dataset B（ABS）：建立 Legal／Reasonable Opportunity arrival、歷史 Challenge behavior 與 2026 external validation。
- Triple-A 三次 Challenge 資料不能混入 MLB 兩次制度的主要 policy fit；只能作行為分析或 sensitivity analysis。
- Full ABS 比賽必須排除。
- 主要 Opportunity 與 Policy dataset 只涵蓋第 1–9 局；延長賽列為未來 extension。

## 九局平手邊界

本次研究不估計延長賽 Challenge policy。九局結束平手時使用固定且可重現的 `Regulation Boundary Value`：主線沿用版本化 Savant external baseline，需做邊界敏感度分析；歷史結果重估移至延伸研究。

此 boundary value 必須在模型訓練前鎖定來源、年份、主客場定義與估計方式。它只提供 regulation-inning terminal value，不生成第 10 局以後的 Opportunity、不模擬 Challenge refill，也不產生延長賽 RRA。

## 時間切分

下列是暫緩的自建 WP 延伸研究切分，不是官方快照的獨立訓練／測試設計：

```text
Train:      2019、2021–2023
Validation: 2024
Test:       2025
External:   2026 MLB
```

所有 preprocessing、encoding、imputation、feature selection、hyperparameter tuning 與 calibration 都只能 fit 在 Train；Validation 用於選型，Test 只在設計鎖定後評估一次。2026 MLB 保留為 prospective／external validation，不參與調參。

同一場比賽的 pitch 不得跨 split。若進行交叉驗證，至少以 `game_pk` 分組，且時間順序不得逆轉。任何隨機 pitch-level split 都視為無效，因為它會把同場狀態與球員資訊洩漏至兩側。

Dataset B 的 Future Opportunity 切分規則另見 [`config/dataset_b_split_plan.json`](../config/dataset_b_split_plan.json)：2024 IL 與 2025 IL 上半年預定 Train，2025 IL 七至八月 Validation、九月 Test，2026 MLB External；39 場已知開發樣本一律隔離。96 場賽程候選已固定；2026-09-29 納入 91 場（原 85 場加嚴格復原 6 場），5 場無法定位官方缺漏 Challenge 而整場排除。限定觀察性到達基線的輸入閘門已通過，但來源資格與完整開發排除尚未驗收，正式 holdout 與策略評估 readiness 仍為 false。這不是上方 Dataset A 自建 WP 切分；2025 Test 也不能稱固定官方 WP 的完全獨立測試。詳見[復原與輸入閘門報告](../reports/archive/phase2/dataset_b_challenge_recovery_2026-09-29.md)。

## 評估指標

固定官方 WP 的外部診斷（或延伸研究自建 WP 的評估）使用：

- Brier Score
- Log Loss
- Calibration curve／reliability table
- 與 Savant WP 的 state-level comparison

不得以 Accuracy 作主要指標。結果至少按 inning、leverage、score differential、base-out state 與 count 分組檢查；同時報告樣本數與 confidence interval，避免小樣本 subgroup 被過度解讀。

Future Opportunity model 應以完整 Legal／Reasonable population 評估 arrival probability 或 time-to-event，不得只用 actual Challenge。Historical Behavior model 才使用 `actual_challenge` 作 outcome，並需處理剩餘額度造成的 censoring／selection bias。

2026-09-29 限定觀察性基線第一版已執行：只在 `provisional_opportunity` 風險集 fit，預測同隊下一個暫定有額度候選的物理投球間隔；`next_opportunity_observed=false` 以右設限 likelihood 處理，不作「永不再到達」負例。Train 43 場只用於估計整體與球數／額度分層 hazard；Validation 12 場選分層模型及收縮強度；Test 12 場與名義 External 24 場只評估一次。對數似然有小幅改善，但 External 的遊戲層級區間含零，Brier 無一致改善。五場缺漏全在 Train，5／48 訓練場次的流失及來源未知限制仍需敏感度分析；不得將此歷史路徑模型用作挑戰後反事實。詳見[基線報告](../reports/archive/phase2/dataset_b_observational_baseline_2026-09-29.md)。

**2026-09-29 後續更正：**舊 `next_opportunity_observed=false` 並非全部為九局右設限；182 筆至少 45 筆有後續零額度候選，另 6 筆剩 1 次挑戰後的結局不明。額度耗盡是行動相關終止，不得繼續把之後投球當作仍可等待有額度機會的曝光。上述 hazard／NLL／Brier 只作歷史紀錄，須以新版行動後額度／終止契約重估；Train 12 個粗粒度雙臂支持格只有 2 格達最低門檻。見[行動與設限稽核](../reports/archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md)。

同日已用既有官方來源將 6 筆結局核對為 5 次失敗／1 次成功，最終為 50 筆即時額度耗盡、132 筆額度仍在的九局設限；後者與 12,950 筆觀察到下一機會一同構成 13,082 筆**事後條件**到達估計母體。此模型由 Train 擬合、Validation 選參、Test／名義 External 評估，額度耗盡另列而不當作右設限；`post_action_budget` 不能當挑戰前特徵。見[額度感知重估](../reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md)。

2026-09-30 的決策時情境原型只允許判決前 Game State、原判、Decision Side、當下額度及固定官方 S0／S1 WP／RE 進入比較。`p`、失敗額度成本及成功分支後續位移均為預先列明的人工敏感度假設；不得從觀察性到達模型的 `post_action_budget` 或已觀測後續球序推入。Test／名義 External 只描述固定候選在這些假設下的行動分布，**不是**政策樣本外勝率、RRA 或因果效果。任一 WP 分支不支援時維持缺值。見[情境規格](../config/policy_scenario_protocol.json)與[原型報告](../reports/archive/phase3/policy_scenario_prototype_2026-09-30.md)。

2026-10-01 的 Phase 2 收尾再次確認：91 場中 7 場進入延長賽，但所有 13,132 筆主候選都在第 1–9 局；完整來源仍保留供官方計數稽核。13,132 筆 ABS 停用／replay 資格皆未知，故 `provisional_opportunity` 不得改稱 Legal。九局平手邊界的 0.25／0.40／0.50／0.60／0.75 主隊 WP 僅為人工壓力測試；只重算當前直接終局的 S0／S1，沒有透過未來狀態傳遞，不能用受影響筆數小推論整體政策穩健。見[收尾驗收](../reports/archive/phase2/official_wp_phase2_closeout_2026-10-01.md)。

後續同日已執行固定五場缺漏的假設性 Train 情境、按起始局數檢查右設限，及「到達後下一次進攻／防守方與 WP 價值類別」的條件分布比較。九局的 20 球結果可觀察比例明顯低於整體；錯誤刪去設限 episode 會推高估計的 hazard。下一 Decision Side 模型的 Test／名義 External log loss 改善；下一 WP 價值類別在名義 External 的遊戲 bootstrap 區間含零，且表外值仍為 `unsupported`。五場缺漏情境不是復原或識別界限，來源選擇偏差仍可能較大。見[延伸敏感度報告](../reports/archive/phase2/dataset_b_followup_sensitivity_2026-09-29.md)。

核心 Dynamic Policy 的決策單位是 Decision Team，僅要求 batting／fielding Decision Side。守方 pitcher／catcher 的精確發起角色不得作核心樣本納入條件；若進行 role-specific Historical Behavior 分析，才可篩選 `exact_role_attribution_complete = true` 的事件。

## Counterfactual 驗證

每個 Challenge situation 必須各自建立：

- \(S_0\)：原判維持。
- \(S_1\)：判決翻轉。

再以同一份已鎖定官方 WP snapshot 分別估值。不得把 observed `delta_home_win_exp` 或 `delta_run_exp` 直接當作 Challenge 的 counterfactual value，因為它們只描述實際發生路徑，沒有估計另一個未發生狀態。

## 可重現性要求

每次正式資料建置或評估必須保存：

- 原始來源 URL 與 query parameters
- UTC retrieval time
- 原始檔 SHA-256 與 byte length
- row count
- rule regime 與 gate requirements 版本／hash
- dataset schema version
- 實際執行版本的程式 commit SHA 與工作目錄狀態；既有未記錄 commit 的開發產物不得追溯宣稱為正式實驗
- Python 與相依套件版本；Phase 0 目前只使用 standard library

正式結果只能來自固定 snapshot，不得在同一報告中混用不同下載時間的可變資料。

## Phase 0 與下一階段

單場 `phase0_game_pass` 只代表該場事件、join、規則與必要欄位通過，不代表整個資料集可行。2026-09-12 的 12 場 snapshot 已由 `validate-phase0` 對所有年度 cohort 與官方 game-record comparison 回傳 `phase0_gate_pass = true`，因此可進入 Phase 1 baseline prototype。此 Gate 是資料管線 smoke test，不取代正式資料集的樣本覆蓋、Legal Opportunity 排除條件與時間切分驗證。延長賽樣本不是 Gate 必要條件，也不進入主要模型範圍。

## 官方 WP 主線新增閘門（2026-09-21）

- 先固定 cohort、母體與覆蓋門檻，再檢查 S0／S1；真實終局、九局平手、超界、複合事件與來源失敗分開計數。不把缺值樣本默默排除。
- 當前兩側可估值不代表 Dynamic 路徑封閉。未來跨界再返回的 continuation、對手策略與決策視野須另行鎖定及做敏感度分析。
- 官方頁面宣告來源 2016–2025，RE 回應標示 2025；不得將 2025 稱為官方 WP 完全獨立 holdout。診斷校準曲線不代表已完成本專案模型訓練／校準。
- Dataset B 必須另行預先鎖定兩次制度的時間切分，按 game_pk 分組；排除所有已參與開發的 2026 場次，不只既知的三場原型。2023–2025 需逐場核對 regime，不直接套用 Dataset A 的年份配置。
- Future Opportunity 不只估計次數，還需到達時間、條件狀態／價值分布及行動依賴轉移。Legal population 受歷史額度影響；c=0 不代表沒有潛在不利判決。需處理 censoring，不能只 fit actual attempts，亦不得用事後 Reasonable label 偷渡成決策特徵。
- technical outage／post-replay-review 尚未完整排除，仍為 provisional_source_limitations。研究結論應受限於來源與估值假設，不把模擬勝率差稱作因果增勝。
