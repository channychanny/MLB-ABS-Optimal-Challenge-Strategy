# Dataset B 訓練前準備與未通過閘門

日期：2026-09-24。這是固定 96 場賽程候選的來源與逐球工程驗收，不是 Future Opportunity 模型訓練，也不是完整 Legal Opportunity 或正式 holdout。選場契約及賽程來源見[賽程候選清冊](dataset_b_schedule_lock_2026-09-24.md)。

後續狀態（2026-09-29）：11 場計數不符中 6 場已用獨立 ABS-only 來源嚴格定位、5 場仍無法定位而整場排除；新版風險集到達標籤與限定輸入閘門見[更新報告](dataset_b_challenge_recovery_2026-09-29.md)。以下數字保留為當時的歷史結果。

## 固定分母與取得結果

本機 `data/processed/dataset_b_population_preparation_2026-09-24-v5.json` 保存逐場狀態、feed／CSV 來源 manifest、輸入檔指紋、規則及對齊結果；`data/processed/dataset_b/candidates_v2/game_<game_pk>.json` 保存 85 場的逐筆暫定候選及到達間隔標籤。這些檔案受 `.gitignore` 排除，不隨 Git clone 自動取得。快取位於 `data/raw/dataset_b/source_cache/`，約 346 MB；舊 v1 候選檔另保留，不覆寫。程式見 [`scripts/prepare_dataset_b.py`](../scripts/prepare_dataset_b.py)。

| 預宣告時間窗 | 選場 | feed／逐球對齊通過 | feed 計數不符 |
| --- | ---: | ---: | ---: |
| 2024 IL Train | 24 | 21 | 3 |
| 2025 IL 前段 Train | 24 | 20 | 4 |
| 2025 IL Validation | 12 | 11 | 1 |
| 2025 IL Test | 12 | 9 | 3 |
| 2026 MLB External | 24 | 24 | 0 |
| 合計 | 96 | 85 | 11 |

全部 96 場均取得官方 feed。11 場的擷取 Challenge attempts／overturned 與官方終場計數不一致，主要是官方多於逐球來源；逐場數值與 `game_pk` 在報告 JSON，沒有刪掉或依結果補場。其中 780340 的 feed 完全沒有 Challenge 事件，官方卻記 1 次成功。通過的 85 場已取得所需 77 個日期的完整 Savant 逐球 CSV，均完成整場物理投球／非投球事件對齊與比數重建。兩場無官方終場 counter 且沒有觀測到挑戰（753330、780436），暫定通過工程對齊，但獨立 counter 核對缺席，不能稱完全驗收。7 場進入延長賽；候選資料固定只取第 1–9 局，不研究延長賽策略。

85 場重建 13,252 個 called-pitch 候選，其中 12,213 個有額度、暫定非位置球員投手的 `provisional_opportunity`，1,000 個零額度候選、39 個明確 position-player pitching 排除。暫定有額度母體的兩側官方 WP 支援為 10,327／12,213（84.56%）；其餘含超出官方表格或複合事件，未截尾、未補零。這不是完整 Legal population 或模型表現。

| Split | 工程通過場次 | 暫定有額度候選 | 兩側 WP 支援 |
| --- | ---: | ---: | ---: |
| Train | 41 | 5,970 | 5,009 |
| Validation | 11 | 1,483 | 1,289 |
| Test | 9 | 1,389 | 1,239 |
| External | 24 | 3,371 | 2,790 |

逐筆候選檔把 `decision_features`、`analysis_labels`、`alignment_evidence`、`arrival_target` 及 `source_eligibility` 分艙。`actual_challenge`、S0／S1 WP 支援或差值、對齊證據、下一次機會的事後標籤均不得充當決策時特徵；特徵只含投球前狀態、剩餘額度、原判、決策方。以同隊下一個暫定候選的物理投球差作觀測到達間隔；若第 1–9 局內未再到達，於 regulation 終點右設限。本次共有 13,082 筆觀測到下一候選、170 筆右設限。這是候選決策點間的**觀察性**序列，不是挑戰後反事實路徑；也尚未驗收為完整 Legal Opportunity 訓練矩陣。

## 來源資格與訓練閘門

85 場 feed 中僅找到 3 個非 ABS review-type 線索，沒有可驗證全場 ABS 技術停用區間或完整 replay 後挑戰時序。[Baseball Savant 官方定義](https://baseballsavant.mlb.com/abs-metrics-documentation)明列技術問題時不能算 Challenge Opportunity；[MLB 規則說明](https://www.mlb.com/news/abs-challenge-system-mlb-2026)指出 replay 後不得挑戰，技術問題期間亦可暫停 Challenge。但這兩頁是規則與指標定義，不提供本樣本逐球停用／replay 時序標記；這是依文件內容及本次 feed 盤點作出的來源限制判斷，不等同證明不存在其他資料源。沒有線索不等於全場可用。13,252 個候選的 `abs_technical_availability`、`post_replay_challenge_eligibility` 均維持 `unknown`；`source_eligibility_status=provisional_source_limitations`。不得把這批資料宣稱為完整 Legal Opportunity，也不能把 2025 Test 稱為固定官方 WP 的獨立樣本外測試。

因此目前 `training_ready=false`、`holdout_game_lists_locked=false`、`formal_model_evaluation_ready=false`。正式訓練前至少仍需：

1. 決定 11 場 feed／counter 不符與 2 場無 counter 的事前、非結果導向納入或缺失規則；不以候選成功率選擇替補。
2. 取得足以定位 technical outage 與 replay 順序的可靠來源，或明確收縮 estimand 並預先鎖定可驗證的敏感度方案；在此之前不升格為完整 Legal population。
3. 逐筆觀察性到達間隔與右設限欄位已備妥，但仍須在正式模型規格中鎖定零額度及位置球員投手的風險集處理、同場相依、歷史挑戰造成的選擇偏差與行動依賴轉移。只拿 `actual_challenge` 或把觀察後續當作挑戰後的反事實路徑均不成立。
4. 固定最終場次清冊、樣本支持與缺失閘門，保證以 `game_pk` 切分，並保存正式執行的 Git commit SHA／工作目錄狀態。

## 重播

取得同一來源快取後，在尚不存在的輸出路徑執行：

```powershell
$env:PYTHONPATH = "src"
python scripts/prepare_dataset_b.py --selection data/processed/dataset_b_schedule_selection_2026-09-24-v3.json --output data/processed/dataset_b_population_preparation_replay.json --offline
```

初次下載來源的 v1、逐球整理 v3 及舊版候選檔均保留。新版 v5 與離線 v6 的 96 筆逐場結果和 77 份 CSV 來源清冊一致；候選檔在離線重播時逐筆核對既存內容，若來源改變則拒絕覆寫。原始快取與候選輸出是本機開發產物，不能追溯宣稱為已記錄 commit 的正式實驗。
