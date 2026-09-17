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

- Dataset A（MLB historical）：訓練 RE／WP 與一般比賽狀態轉移；2020 不納入主要模型。
- Dataset B（ABS）：建立 Legal／Reasonable Opportunity arrival、歷史 Challenge behavior 與 2026 external validation。
- Triple-A 三次 Challenge 資料不能混入 MLB 兩次制度的主要 policy fit；只能作行為分析或 sensitivity analysis。
- Full ABS 比賽必須排除。
- 主要 Opportunity 與 Policy dataset 只涵蓋第 1–9 局；延長賽列為未來 extension。

## 九局平手邊界

本次研究不估計延長賽 Challenge policy。九局結束平手時使用固定且可重現的 `Regulation Boundary Value`：Phase 1 優先採 Savant external baseline，Phase 2 再以固定歷史期間中「九局結束平手」比賽的最終勝率重估。

此 boundary value 必須在模型訓練前鎖定來源、年份、主客場定義與估計方式。它只提供 regulation-inning terminal value，不生成第 10 局以後的 Opportunity、不模擬 Challenge refill，也不產生延長賽 RRA。

## 時間切分

正式 WP 模型使用固定時間切分：

```text
Train:      2019、2021–2023
Validation: 2024
Test:       2025
External:   2026 MLB
```

所有 preprocessing、encoding、imputation、feature selection、hyperparameter tuning 與 calibration 都只能 fit 在 Train；Validation 用於選型，Test 只在設計鎖定後評估一次。2026 MLB 保留為 prospective／external validation，不參與調參。

同一場比賽的 pitch 不得跨 split。若進行交叉驗證，至少以 `game_pk` 分組，且時間順序不得逆轉。任何隨機 pitch-level split 都視為無效，因為它會把同場狀態與球員資訊洩漏至兩側。

## 評估指標

WP model 主要使用：

- Brier Score
- Log Loss
- Calibration curve／reliability table
- 與 Savant WP 的 state-level comparison

不得以 Accuracy 作主要指標。結果至少按 inning、leverage、score differential、base-out state 與 count 分組檢查；同時報告樣本數與 confidence interval，避免小樣本 subgroup 被過度解讀。

Future Opportunity model 應以完整 Legal／Reasonable population 評估 arrival probability 或 time-to-event，不得只用 actual Challenge。Historical Behavior model 才使用 `actual_challenge` 作 outcome，並需處理剩餘額度造成的 censoring／selection bias。

核心 Dynamic Policy 的決策單位是 Decision Team，僅要求 batting／fielding Decision Side。守方 pitcher／catcher 的精確發起角色不得作核心樣本納入條件；若進行 role-specific Historical Behavior 分析，才可篩選 `exact_role_attribution_complete = true` 的事件。

## Counterfactual 驗證

每個 Challenge situation 必須各自建立：

- \(S_0\)：原判維持。
- \(S_1\)：判決翻轉。

再以同一個已鎖定 WP model 分別估值。不得把 observed `delta_home_win_exp` 或 `delta_run_exp` 直接當作 Challenge 的 counterfactual value，因為它們只描述實際發生路徑，沒有估計另一個未發生狀態。

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
