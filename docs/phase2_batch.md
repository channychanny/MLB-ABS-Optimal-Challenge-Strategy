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

exit code 0 表示所選場次全部通過；1 表示缺來源、空日期或有被排除場次，且報告已保存；2 表示計畫、參數或輸出路徑錯誤。這批目前預期回傳 1，不能當作全數通過。

## 已知缺口與下一步

本次發現敬遠保送與計時器違規的自動判決會使 Statcast 列數與 feed 真正投球不同；計時器事件還可能造成後續實際投球編號錯位。核心建置器尚未做重新對齊，整場排除保護仍保留。不能只刪掉 automatic_ball／automatic_strike 再直接按舊三欄 join。詳見 [Issue 06](../.scratch/phase2-models/issues/06-no-pitch-alignment.md)。

目前樣本沒有通過稽核的再見或九局平手場次，這兩類真實資料驗證仍未完成；11+ 分也只有一場，不足以宣稱估值可靠。正式全季下載與 WP 訓練前先關閉對齊問題，並補足覆蓋與版本條件。

使用者已確認尚未設定 Git。可繼續管線開發，但正式模型訓練前仍需本機 repository 與 commit；不要求一定上傳 GitHub，本輪未初始化或提交。
