# 07 — 建立 Phase 1 RE／WP Baseline

Type: task  
Status: resolved

## 前置狀態

Phase 0 已於 2026-09-12 通過。這只證明資料管線可行，不代表正式資料集與模型已完成。

## 範圍（2026-09-14 依產品規格第 30 節校正）

- 建立帶有來源、時間與 SHA-256 的 Savant RE288／含球數 WP snapshot。
- 對已通過 Phase 0 的少量兩次額度比賽，重建原判維持及翻判的兩種狀態，分別查表估值。
- 固定九局平手的外生 Regulation Boundary Value，不產生延長賽決策。
- 用明確標示的合成情境跑通簡化 Dynamic pipeline；不將它當作已訓練策略或歷史回測。
- 子項與驗收進度見 [Phase 1 工作地圖](../../phase1-baseline/map.md)。

## 移交後續階段的原始範圍

- 鎖定 Dataset A 的固定 snapshot、來源 manifests、Python／相依套件版本與可追溯 commit SHA。
- 依 `docs/evaluation_design.md` 實作 game-level temporal split：Train 2019、2021–2023；Validation 2024；Test 2025；2026 MLB 只作 external validation。
- 建立 regulation-inning RE／WP baseline 與 calibration 報告。
- 明確版本化九局平手的 Regulation Boundary Value；不模擬第 10 局以後的 Challenge policy。
- 補齊 ABS technical outage 與 post-replay-review 的 Legal Opportunity 排除，未完成前維持 `provisional_source_limitations`。
- 在正式 Historical Behavior 結論前擴大 Triple-A 日期、月份與判決方向覆蓋，並量化 player-role／position-player-pitching metadata 缺失；Phase 0 已各自 smoke-test International League 與 Pacific Coast League。

## 非範圍

- 正式 Future Opportunity model、RRA final estimate；合成情境 Dynamic prototype 仍在 Phase 1 範圍。
- 延長賽 Challenge refill、arrival 或最佳使用策略。

## 後續正式模型驗收條件（非 Phase 1 完成條件）

- 所有 feature 的 `as_of_date` 與 fit scope 可稽核，沒有同場或未來資料洩漏。
- 同一 `game_pk` 不跨 split，preprocessing 與 calibration 只依規定 split fit。
- Brier Score、Log Loss、calibration 與 Savant state-level comparison 可重現。
- Legal Opportunity 已完成兩項排除，或明確阻擋後續 Dynamic Policy，不得靜默視為完成。

## Comments

- 2026-09-14：原 Issue 混入 Phase 2 訓練與校準，並誤將所有 Dynamic Programming 排除；此次依既有產品規格修正，保留原項目作後續追蹤，不取消防洩漏或 Legal population 要求。
- 2026-09-15：官方 v2 snapshot、狀態估值與合成 Dynamic 流程已完成，103 項測試通過。兩場／10 次完整估值通過；三場／16 次整體仍有 4 次超出表格範圍，維持 partial。最終範圍驗收由 Phase 1 Issue 05 追蹤，尚未將整個階段標記完成。

## Answer

2026-09-15 後續使用者明確同意官方 ±5 分限定驗收並啟動 Phase 2，本 Issue 關閉。原三場部分結果不變；自建模型與全比分驗證改由 [Phase 2 工作地圖](../../phase2-models/map.md) 追蹤。
