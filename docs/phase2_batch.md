# Phase 2 批次下載、續跑與開發資料清單

## 目的與邊界

本流程實作 [Issue 03](../.scratch/phase2-models/issues/03-snapshot-version.md) 的下載工程與跨年度小批次驗證，不代表正式資料集已定稿或模型已訓練。

版本化計畫在 [config/phase2_sample_plan.json](../config/phase2_sample_plan.json)：2019、2021–2024 各取 5 月 15 日與 8 月 15 日，從當日已結束、例行賽、原訂九局制場次按 game_pk 升冪取兩場。這是固定工程抽樣，不是隨機代表性樣本，不依比分、勝負或稽核是否成功更換場次。

2025／2026 與 2020 不能放進此命令的計畫。`games_per_date=null` 代表指定日期的全部候選場次；空日期不代表全季，日期清單仍必須明列。全季大量執行前仍需完成來源差異與資源評估。

## 來源、快取與完整性

1. 每年保存整季官方 schedule 原始回應與 manifest。保留延期／重列紀錄，按 game_pk 去重；日期或主客隊身分矛盾則列為排除，不猜測。
2. 每個選定日期只下載一份完整 MLB Statcast CSV，供該日所有選定場次共用。
3. 每場保存官方 feed，先與清冊的 game_pk、日期及主客隊核對，再交由既有 Dataset A 建置器處理。
4. 每份來源以 URL 雜湊作檔名，內含原始文字、完整 URL／query、UTC 時間、SHA-256、byte length、row count；使用前重新計算，損毀時報錯且保留原檔。
5. 寫入在同目錄暫存檔完成並同步後，以不可覆寫的原子方式發布。若中斷，只清理由本次建立的暫存檔；成功來源不受影響。此實作需要檔案系統支援硬連結；目前 Windows NTFS 實測通過。
6. 408／429／選定 5xx、暫時連線失敗最多嘗試三次；404、資料格式錯誤或指紋損毀不會反覆下載掩蓋問題。採循序請求，沒有高併發下載。

快取是固定快照，重跑不會自動更新來源。要取得新下載版本，使用新的快取目錄，舊目錄保留。

## 衍生分片與開發 lock

每場獨立儲存 `historical-shard-v1`，包含來源 hash、契約 hash、程式內容指紋與完整 Dataset A 結果。成功與整場排除都保存；換程式或換來源會產生新分片，不覆寫舊結果。

批次報告中的 `dataset_lock` 保存計畫、來源 manifests、各年度清冊、選定日期、各場接受／排除／失敗、衍生內容 hash。`dataset_lock_sha256` 可比較兩次是否使用完全相同的開發材料；它不是數位簽章，也不取代正式模型的 commit SHA。

`execution` 的下載／重用計數在重播時本來就會不同，因此不參與 lock 指紋。相同來源、契約、程式及選樣下，線上首次執行與離線重播應產生相同 lock。

來源下載完整與稽核通過分開：

- `complete_selected_sources=true`：選定來源都已取得且有逐場稽核結果，可以包含 audit_excluded。
- `all_selected_games_accepted=true`：所有選定場次均通過。
- `full_season_coverage_verified=false`、`formal_training_ready=false`：目前始終保留，不因清冊列出全季或小樣本成功而升級。

## 執行方式

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m abs_challenge.cli run-historical-batch --plan config/phase2_sample_plan.json --cache-dir data/raw/phase2_cache_2026-09-16 --artifact-dir data/processed/phase2_batch_2026-09-16 --output data/processed/phase2_batch_next_report.json
```

續跑使用同一計畫、快取與 artifact 目錄，但報告路徑要換新檔名。已驗證來源重用；只有之前未完成的下載會再嘗試。中斷時尚未產生最終報告也可重跑，先前逐場成果仍存在。

離線重播加上 `--offline`：

```powershell
python -m abs_challenge.cli run-historical-batch --plan config/phase2_sample_plan.json --cache-dir data/raw/phase2_cache_2026-09-16 --artifact-dir data/processed/phase2_batch_2026-09-16 --offline --output data/processed/phase2_batch_next_replay.json
```

exit code 0 表示所選場次全部通過；1 表示缺來源、空日期或有被排除場次，且報告已保存；2 表示計畫、參數或輸出路徑錯誤。舊版 2026-09-16 批次回傳 1；2026-09-18 v2 使用同一來源與選樣回傳 0，不代表全季資料通過。

## 已知缺口與下一步

敬遠保送與計時器違規的自動判決會使 Statcast 列數與 feed 真正投球不同，並可能造成後續實際投球編號錯位。[Issue 06](../.scratch/phase2-models/issues/06-no-pitch-alignment.md) 已以獨立對齊器核對事件、判決、球數及跑者狀態；未知型態仍整場排除，不可只刪自動判決後按舊三欄 join。批次 `summary.alignment` 保存非投球、跨來源編號不同、通過狀態核對的投球，以及無投球打席數量。

固定 20 場全數通過後，新增 2 場九局平手，但兩場最終均主隊贏，開發平均 1.0 不具可採用的統計支持。仍沒有真實再見半局，11+ 分也只有一場。全季下載與 WP 訓練前仍需補足覆蓋、排除偏差與版本條件。

Git 基準已依使用者授權建立；對齊修正的本輪執行記錄為 `worktree_clean=false`，仍是開發結果。驗證指令與前後比較工具見 [事件對齊報告](../reports/archive/phase2/phase2_alignment_validation.md)。舊來源、分片與報告均保留，新程式內容指紋會產生新分片，不覆寫舊檔。

## 跨月份擴大樣本

後續全季取得已於 2026-09-19 啟動：依固定清冊逐月全取，首月 2019-03 已完成；使用方式及容量限制見 [全季取得說明](phase2_season_acquisition.md)。以下仍保留原工程抽樣流程，不能將兩者的選樣範圍混用。

[擴大計畫](../config/phase2_expanded_sample_plan.json) 固定五年度 4–9 月每月 15 日、每日最多三場，最多 90 場。沒有例行賽的日期保留 `no_eligible_games`，不另找日期替換。這仍是工程抽樣；原有來源重用固定快照，新來源保存各自取得時間，不宣稱為同一瞬間下載的全季快照。

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m abs_challenge.cli run-historical-batch --plan config/phase2_expanded_sample_plan.json --cache-dir data/raw/phase2_cache_2026-09-16 --artifact-dir data/processed/phase2_expanded_2026-09-18_network --output data/processed/phase2_expanded_next.json
python scripts/summarize_historical_coverage.py --report data/processed/phase2_expanded_next.json --artifacts data/processed/phase2_expanded_2026-09-18_network --output data/processed/phase2_expanded_coverage_next.json
```

離線重播在第一個命令加 `--offline` 並換新的輸出檔名。報告工具核對 lock、選樣清單、分片及 Dataset A 指紋，按年度／月份保留全部選定場次作分母；來源失敗與稽核排除分開列出。按 Train／Validation 分列分差支持、再見半局及九局平手，RE 仍只 fit Train。

`not_accepted_fraction` 是該工程樣本的描述比例；不是全季排除率估計。輸出完整 Train-only RE 格子及各格場次，沒有觀測仍為 null，少數場次或混合年度的九局平手平均仍不供正式估值。報告不計算 WP 信賴區間或宣稱模型可靠。

本輪新來源差異追蹤於 [Issue 07](../.scratch/phase2-models/issues/07-expanded-alignment.md)。`complete_selected_sources` 在有空日期時按現行契約為 false；要分辨是否真的缺來源，應同時查看 `date_status_counts` 及逐場失敗類型。命令回傳 1 可能來自有排除場次或空日期，不等於下載程式崩潰。

2026-09-19 Issue 07 已完成，使用同一快取及計畫、另存於 `data/processed/phase2_issue07_2026-09-19/`，84 場／24,448 球通過。50 筆 CSV 自動判決與 5 筆 feed-only N 事件分開保存；後者在逐場 `alignment.feed_only_events`，不計入批次 `non_pitch_rows`。兩個空日期仍使命令回傳 1；逐場接受結果及重播證據見 [最新驗證報告](../reports/archive/phase2/phase2_issue07_validation.md)。
