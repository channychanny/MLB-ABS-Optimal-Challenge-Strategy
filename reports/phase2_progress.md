# Phase 2 啟動與第一個工作切片

更新日期：2026-09-15  
狀態：**Dataset A 與 RE 開發流程已跑通；Phase 2 整體未完成，WP 尚未訓練。**

2026-09-16 後續更新：已新增批次快取、續跑與五年度固定小樣本。20 場中 15 場／4,303 球通過，5 場非投球對齊待處理，詳見 [跨年度批次報告](phase2_batch_validation.md)。本頁下方保留第一個工作切片的歷史驗證紀錄。

## 已完成

- 依使用者同意關閉 Phase 1 的 ±5 分限定驗收，保留原本 4 次越界缺值紀錄。
- 新增 Dataset A 來源 bundle、完整投球／比分核對、決策前特徵白名單、最終勝負與半局剩餘得分標籤。
- 固定 Train 2019／2021–2023、Validation 2024、Test 2025、External 2026；2026 已知開發三場另列。
- 保留未截尾分差，分 0–5／6–10／11+ 統計支持度。
- 新增 Train-only RE24／RE288 與九局平手邊界的開發估計命令，空樣本保留 null。
- 136 項標準函式庫測試通過（原 103 項＋新增 33 項），不依賴網路或本機資料。

## 真實 Train 年度小樣本

選用 2019-06-01 的 MLB 比賽 `564960`，舊金山客場對巴爾的摩，終場客隊 8：2。此場依比分與完整性選作工程案例，不作無偏統計抽樣。

| 核對項目 | 結果 |
|---|---:|
| 當日原始 CSV | 4,574 列 |
| 選定場次的第 1–9 局投球 | 283 |
| 主隊投球計數 | 152 |
| 客隊投球計數 | 131 |
| 缺漏／多餘投球 | 0／0 |
| 絕對分差 0–5 | 249 球 |
| 絕對分差 6–10 | 34 球 |
| 絕對分差 11+ | 0 球；尚無真實驗證樣本 |
| RE24 有觀測格 | 15／24 |
| RE288 有觀測格 | 88／288 |
| 九局平手樣本 | 0；邊界值 null |

**這只證明大比分資料可以進入自建流程，不代表已有準確的大比分 WP。** 沒有取用 2025／2026 真實資料來調參，也沒有用一場資料宣稱全季 RE 或主隊勝率已訓練完成。延長賽勝負標籤與再見 RE 排除目前由合成測試驗證，還需真實跨年度樣本稽核。

來源在 bundle 內保存：[官方比賽 feed](https://statsapi.mlb.com/api/v1.1/game/564960/feed/live)及 2019-06-01 完整 Statcast 查詢。投球前欄位依 [官方 CSV 說明](https://baseballsavant.mlb.com/csv-docs)解析。

## 可重播成果

本機檔案受 `.gitignore` 排除，新 clone 不預設存在：

- `data/raw/historical_564960_2026-09-15.json`
- `data/processed/dataset_a_564960_verified_2026-09-15.json`
- `data/processed/dataset_a_564960_verified_2026-09-15_replay.json`
- `data/processed/re_development_564960_verified_2026-09-15.json`

兩份 `verified` Dataset A 的完整檔案 SHA-256 相同：

```text
324f5dce29b0b725c883bcf8887640da8e79fd2bdacb545780e23405c0de06f7
```

先前不含 `verified` 的小樣本衍生檔保留為開發紀錄；上述新檔才包含補強後的官方投球總數核對 metadata。沒有覆寫舊資料。

## 尚未完成與下一步

1. 建立正式 Dataset A 全季來源清冊、擴大各 Train 年度與 2024 Validation 覆蓋；下載器需改為逐日共用快取，不能逐場反覆下載同一天。
2. 取得可追溯的專案 commit 與 dataset lock。目前 Git 仍無法解析專案版本，沒有自行初始化、重建或提交。
3. 建立 Logistic Regression WP、Train 內獨立校準期間與分組評估，再決定是否需要 GAM／XGBoost。
4. 以正式歷史樣本估計 RE 與九局平手邊界，處理再見排除偏差、年度規則差異及信賴區間。
5. 將通過校準的 WP 接回反事實／Dynamic 原型，才處理 Phase 2 最終驗收。正式策略仍受 Dataset B Legal Opportunity 缺口限制。

工作分解與狀態見 [Phase 2 地圖](../.scratch/phase2-models/map.md)。
