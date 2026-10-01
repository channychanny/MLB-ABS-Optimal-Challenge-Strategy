# 04 — WP Model A 訓練、校準與評估

> 2026-09-21 排程更新：自建 WP 與全季資料擴充改列延伸研究，本 Issue 暫緩而非完成。保留以下歷史紀錄與重啟驗收條件；目前主線見 [官方 WP 工作地圖](../../official-wp-policy/map.md)。

Type: task  
Status: open
Execution: deferred
Blocked by: 01, 03

## 驗收條件

- 先建立只含 Game State 的 Logistic Regression baseline，分差保留原值；再按 Validation 結果決定是否需要 GAM／XGBoost。
- preprocessing 與 calibration 只 fit Train；校準使用 Train 內較晚期間的獨立比賽，不可直接用基模型訓練列校準。具體內部日期需在訓練前鎖定。
- Validation 2024 選型；Test 2025 設計鎖定後評估一次；2026 external 不調參。
- Brier、Log Loss、reliability table，按局數、分差、壘包／出局、球數與可用的 leverage 分組；信賴區間以比賽為重抽樣單位。
- 檢查翻判前後價值方向、極端比分、不合理狀態及資料稀少區域，不以截零掩蓋問題。
