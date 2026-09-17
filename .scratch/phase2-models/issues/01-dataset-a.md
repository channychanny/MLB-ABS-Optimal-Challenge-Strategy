# 01 — Dataset A 建置與時間切分

Type: task  
Status: resolved

## 範圍

從完整 Statcast 逐球資料與官方終場 feed 建立第 1–9 局的特徵、最終主隊勝負與原半局剩餘得分標籤。保留投打兩方所有觀測投球，不限實際 Challenge。

## 驗收條件

- 拒絕重複鍵、逐球缺漏、非 MLB、非例行賽、非九局制與未完成比賽。
- 同場固定年度 split；Train 2019／2021–2023，Validation 2024，Test 2025，External 2026。
- 主隊真實分差不截尾，按 0–5／6–10／11+ 分報告覆蓋。
- 特徵白名單不含球位、翻判、observed WP 或 delta；來源 hash、缺值與排除原因可追查。
- 2026 已使用的三場列為 development，不作獨立 external 證據。

## Answer

2026-09-15：`historical.py`、`historical_sources.py` 與 Phase 2 CLI 已完成此工程切片。官方 2019 年 `564960` 的 283 球與逐球鍵／兩隊投球總數一致，34 球分差超過 5 分原樣保留。整體 136 項測試通過；全季資料覆蓋不是本 Issue 的完成宣稱，移交 Issue 03。
