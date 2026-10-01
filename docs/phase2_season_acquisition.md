# Phase 2 全季清冊與逐月取得

## 範圍與版本

本流程是 Issue 03 的資料取得工程，使用 Train 2019／2021–2023 及 Validation 2024。2025 Test／2026 External 不進入計畫。全季清冊完整、某月下載完成、逐場稽核通過、正式訓練資料鎖定是不同條件。

`scripts/plan_historical_seasons.py` 只讀既有固定快取，重新核對五年度官方賽程及參考批次的來源／分片指紋。依月份列出全部候選 game_pk、明確日期及來源 manifests，生成帶有 `campaign_sha256` 的取得計畫。清冊排除（如原訂七局制）另存，不靜默消失。

每月沿用 `historical-batch-plan-v1` 的工程執行介面，`games_per_date=null` 表示該月列明日期的全部候選，沒有每日抽樣上限。`purpose=engineering_sample` 是既有建置器的開發階段標籤；本計畫按清冊全取，不因保留此標籤便變成每天抽三場。`formal_training_ready` 與 `full_season_coverage_verified` 保持 false。

2026-09-19 固定計畫共 36 個月、913 個比賽日、12,029 場候選；2021 年清冊另有 121 場因原訂非九局制排除。這是取得目標，並不表示 12,029 場逐球資料已存在。

## 容量評估

以既有 84 場與 28 日來源實際檔案大小估算，一版全季來源及分片約 16.98 GiB（樣本平均乘目標數），或 21.83 GiB（各類樣本最大值乘目標數）。這不是信賴區間或保證上限，也未包含後續重建版本與模型產物。規劃時 C 槽剩餘約 21.46 GiB，扣除 5 GiB 保留額後不足以穩妥容納全部未壓縮產物。

因此先逐月執行並驗證容量與重播。大量後續取得前，須採可驗證的壓縮儲存或足夠容量的資料目錄；不自動刪除既有來源騰空間。執行器每次來源讀取／下載前檢查磁碟，低於 5 GiB 則停止，已成功的快取與分片可供續跑。這是逐次檢查，不是磁碟配額；其他程序仍可能同時消耗空間。

月批次也限制建置器一次累積的覆蓋統計量；不把五年數百萬球放進同一批記憶體。容量報告保存參考批次及計畫工具的檔案指紋。

## 準備及執行

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python scripts/plan_historical_seasons.py --cache-dir data/raw/phase2_cache_2026-09-16 --reference-report data/processed/phase2_issue07_2026-09-19_verified.json --reference-artifacts data/processed/phase2_issue07_2026-09-19 --output data/processed/phase2_season_campaign_new.json
python scripts/run_historical_month.py --campaign data/processed/phase2_season_campaign_new.json --month 2019-03 --cache-dir data/raw/phase2_cache_2026-09-16 --artifact-dir data/processed/phase2_seasons_2026-09-19 --output data/processed/phase2_month_2019-03_new.json
```

已有固定計畫可直接執行第二個命令；不要每次重新生成計畫。後續月份改 `--month`，順序及所有月份列在取得計畫內。啟動每月前，執行器會離線重建固定清冊並逐欄比較；來源清冊、月份或選樣變更，即使手動重算 hash 也會拒絕。

每月結果記錄原建置器的來源／資料 lock、campaign hash、預定場次、實際 runtime、contract 與兩支腳本 manifests。完成時還會核對實際選定 game_pk 是否與預定清冊完全一致。

離線重播加 `--offline`，並使用新的報告檔名。來源失敗可在相同計畫／快取／分片目錄續跑；已完成資料不重下載、不覆寫。缺空間中止時可能尚無最終月報，已發布的分片仍存在。

清冊、來源與分片保存於 Git 忽略的 `data/`；新 clone 需要先取得原固定快取與參考批次，或依前述工程樣本流程重新建立自己的來源版本。新下載不保證與舊來源逐 byte 一致。

## 正式鎖定前仍需完成

- 逐月取得並稽核全部預定候選，將資料排除與來源失敗分開量化。
- 針對來源排除模式、跨日補賽、縮短比賽及稀有狀態檢查偏差。
- 彙總月份前驗證相同契約、來源快照與版本，防止重複 game_pk 或漏月；不能只加總各月成功數。
- 固定可追溯且乾淨的實際程式版本及環境，再產生正式 dataset lock。當前未提交工作目錄的結果仍屬開發驗證。
- 完成上述條件後，才進入正式 WP 訓練與校準；Dataset B 的限制仍獨立追蹤。
