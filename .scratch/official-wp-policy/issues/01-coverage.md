# 01 — 官方 WP 覆蓋率驗證

Type: task  
Status: claimed

## 目標

量化固定官方表格對主要研究母體的支援程度；不把三場 12／16 的原型結果當成全季結論。

## 工作與驗收

- 執行前鎖定 cohort：比賽清單、日期、抽樣理由、兩次制度與 format 證據；樣本數及覆蓋容忍門檻須預先說明，不依結果反向挑選。
- 分開報告 actual attempts 與 provisional opportunity population。不得因無實際挑戰而排除整場，或把需要事件證據的格式未知場次自行升級 confirmed。
- 為所有選定比賽保留處理狀態；來源失敗／規則未知列入流程分母，合法性未知與查表不支援分開，不默默刪除。
- 對純判決轉移檢查 S0／S1，列出雙側支援、單側缺失、雙側缺失；合法勝負終局與九局平手另列。記錄複合事件、無效狀態及來源問題。
- 按年度／regime、比賽、Decision Side、局數、真實分差與 count 報告分母、支援數、比例及支持量。只對明確定義的母體報告覆蓋率。
- 保存來源、官方快照 hash、cohort、程式 commit／dirty 狀態、命令與輸出 manifest；提供離線重播及合成邊界測試。
- 測試涵蓋 +5 到 +6、−5 邊界、保送、三振換邊、再見、九局平手、複合事件與主客視角；既有 Phase 1 結果不得意外改變。
- 報告明確指出：當前估值支援不代表未來 Dynamic 路徑支援；本 Issue 不完成正式策略。

報告可在覆蓋不足時完成，但不得因此把研究支援性閘門標為通過；需提出縮限或邊界設計選項。

## Comments

2026-09-22：完成五球診斷／回歸修正，actual attempts 更新為 22／29；補齊固定六場完整來源，1,876 球通過事件對齊與比分核對，1,042 個候選中 962 個暫定機會、80 個零額度。暫定機會 706／962 兩側支援。214 項測試通過、兩次離線 lock 相同。見 [完整逐球報告](../../../reports/archive/phase2/official_wp_opportunity_coverage.md)。跨年度、代表性抽樣與來源資格限制仍未完成，維持 claimed。

2026-09-23：24 場 feed、9 日完整逐球與 ABS-only CSV 已取得；分層、來源與執行均可離線重播。2025 IL/PCL 制度已按 league ID 拆開。兩次制 18 場中 17 場完成 provisional opportunity alignment，2,156／2,346 有額度候選兩側皆可查 WP；零額度另列，780464 全場保留為 alignment failure。直接 Challenge audit 與機會歷史對齊是不同檢查：2024 AAA ABS-only 匯出無挑戰列、824087 三鍵直接 join 遭自動好球列位移，但 event alignment 可核對 ledger。詳見 [跨年度清冊與資格來源盤點](../../../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。

2026-09-24：以打者逾時 violation 證據嚴格辨識 `AB` 非投球自動好球，780464 打席 53 完成對齊；固定 lock 離線重播後主要兩次制 18／18 場通過，原 17 場逐場分類未變。現有額度暫定機會 2,218／2,489 雙側可查（89.11%），零額度 262 個另列；780464 新增 143 個候選中 79 個兩側超界。223 項測試通過，正式 readiness 仍為 false。見 [跨年度清冊與資格來源盤點](../../../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。

2026-09-24 分組續作：v8 離線重播新增母體隔離的年度／regime、比賽、Decision Side、局數、真實分差及 count 分組；主要有額度候選總數未變。2024 IL 829／937、2025 IL 702／834、2026 MLB 687／718 雙側可查；兩側不可查的 142 個全在第 5–9 局，且 123 個集中於 780464、753323。這是描述性工程樣本，不能當成代表性覆蓋估計；見[報告](../../../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。

2026-09-24 逐筆缺值續作：v9 離線重播新增 289 筆未雙側估值候選的來源事件鍵與 S0／S1 結構化原因。有額度 271 筆中，142 筆雙側超界、2 筆單側超界（另一側均為合法 `home_win` 終局）、127 筆尚未進行純判決查表；286 個不可查分支均為轉移後真實分差超出 ±5。零額度 18 筆未雙側估值皆屬查表前排除。總數及選樣 SHA 未變；225 項測試通過。見[報告](../../../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。

2026-09-21 第一輪開發子母體完成：6 場全部重新稽核，29 次 regulation attempts 中 17 次兩側支援、7 次兩側超界、5 次純判決出局數不符；3 次延長賽另列。208 項測試通過，離線重播 lock 相同。詳見 [報告](../../../reports/archive/phase2/official_wp_coverage_development.md)。

本 Issue 不關閉：完整機會母體資格（ABS outage／post-replay eligibility）未知，抽樣代表性、分組不確定性及未來分支求值尚未驗收；樣本為工程開發 cohort，非代表性抽樣或 holdout。下一步處理來源資格、continuation 設計及正式時間切分；正式 readiness=false。
