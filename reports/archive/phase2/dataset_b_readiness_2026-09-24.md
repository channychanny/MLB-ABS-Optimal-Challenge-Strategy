# Dataset B 資格來源與時間切分預備盤點

日期：2026-09-24。此報告是 Phase 2 Issue 02／04 的工程準備，不是完整 Legal Opportunity 驗收、正式訓練或樣本外評估。

## 官方規則與本機證據的分界

[Baseball Savant 的 ABS 指標定義](https://baseballsavant.mlb.com/abs-metrics-documentation)把技術問題期間排除在 Challenge Opportunity 之外；[MLB 的 2026 ABS 說明](https://www.mlb.com/news/abs-challenge-system-mlb-2026)指出 replay review 後不得再發起 ABS Challenge，技術故障期間也會暫停接受挑戰。這些規則不能證明特定逐球是否符合資格。

使用既有快取執行 `PYTHONPATH=src python scripts/acquire_official_wp_expansion.py --offline --output data/processed/wp_expansion_acquisition_2026-09-24-v11.json`。24／24 場 feed 均完成訊號盤點，共有 78 個逐球 `reviewType=MJ` ABS review；此數不是官方 attempts 總數，因部分終局挑戰只存在打席結果文字。在目前掃描的逐球 action 描述／event type 及非 ABS review type 中沒有命中 replay 或技術問題線索。**沒有線索不等於沒有停用或 replay**：feed 沒有經驗證的全場 ABS 停用區間與逐球 replay ordering 來源。因此 2,751 個候選的 `abs_technical_availability` 與 `post_replay_challenge_eligibility` 均為 `unknown`，不因看見 ABS review 或無文字命中而升級為已確認合法。

v11 的來源與選樣 SHA、候選 2,751、兩次制有額度暫定機會 2,489、雙側 WP 支援 2,218 均與 v9 相同；只新增逐場訊號盤點及逐球資格未知欄位。v11 本機 JSON 與原始 feed 受 `.gitignore` 排除，不隨 Git clone 提供。來源訊號掃描只是針對現有 feed 欄位的線索盤點，不是對所有可能的廣播公告、影片或官方內部記錄的否定證明。

目前可描述的 estimand 僅為：**已確認兩次挑戰制度、例行賽第 1–9 局、資料可見的 called ball／strike 不利判決，依可重建歷史額度與可辨識投手資格建立的 provisional candidates**。零額度候選另列；投手資格未知與野手登板另列／排除。技術停用與 replay 後資格未知仍留在母體標記，不得將這 2,489 個稱為官方完整 Legal Opportunity。正式研究需取得可驗證的逐球資格來源，或預先縮限研究問題並對未知資格做敏感度分析。

## Dataset B 時間切分規則（尚非已取得的資料集）

規則版本見 [`config/dataset_b_split_plan.json`](../config/dataset_b_split_plan.json)。只接受 feed 規則已確認的兩次挑戰制度；2023 格式混合及 PCL 三次制度不能自動混入主要 fit。場次以 `game_pk` 為單位，任何已知開發場優先標 `development_only`，不可升格成 Validation／Test／External。

| 用途 | 預宣告時間窗及制度 | 現況 |
| --- | --- | --- |
| Train | 2024-06-25–09-30 的 2024 IL 兩次制；2025-03-01–06-30 的 2025 IL 兩次制 | 新場清冊待鎖 |
| Validation | 2025-07-01–08-31 的 2025 IL 兩次制 | 新場清冊待鎖 |
| Test | 2025-09-01–09-30 的 2025 IL 兩次制 | 新場清冊待鎖 |
| External | 2026-04-01–09-30 的 2026 MLB 兩次制 | 新場清冊待鎖；既有 2026 開發場全部排除 |

已知開發排除清冊有 39 場，涵蓋 Phase 0 的 12 場、官方 WP 六場先導，以及跨年度 24 場工程 cohort 的聯集；來源檔在 split plan 中列明。這是目前能追溯的**已知**清冊，尚須在正式鎖定前檢查其他曾供程式調整的樣本。2025 的 Test 可檢查 Future Opportunity 模型的時間泛化，**不能**宣稱固定官方 WP 快照對 2025 完全樣本外。

[`dataset_b_split.py`](../src/abs_challenge/dataset_b_split.py) 會拒絕重複 `game_pk`、交疊時間窗與時間倒序；規則或制度未確認的場次不會落入主要 split。這些只是預宣告規則：新候選場次的抽樣方法、數量、game_pk 清冊與來源 manifest 尚未鎖定，故 `holdout_game_lists_locked=false`、`formal_model_evaluation_ready=false`。本輪沒有下載全季資料或訓練模型；不得用已看過的 24 場回填為「未見」測試。

## 後續閘門

1. 在取得新場資料前，先鎖定可負擔的抽樣方法、每個時間窗樣本量及完整開發排除清冊；抽樣不得依 WP 覆蓋結果或模型表現補選。
2. 取得新場的 game-level metadata 與來源 manifest，逐場驗證 Challenge format／兩次額度，再產生不可跨場的 Train／Validation／Test／External 清冊。
3. 若仍無逐球停用／replay 資格來源，明確採 provisional estimand 並設未知資格敏感度分析；不得稱完整 Legal population。
4. 之後才開始 Future Opportunity 基線的訓練、校準及未見資料評估。
