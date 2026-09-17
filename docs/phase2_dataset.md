# Phase 2：Dataset A 與 RE 開發契約

## 目前階段

Phase 1 已由使用者同意以官方 ±5 分範圍限定驗收。Phase 2 第一個工作切片實作了來源快照、歷史狀態／標籤、年度切分與 RE 開發估計；**WP 訓練、校準與替換估值來源尚未完成**。

規格入口：[產品規格第 30 節](../MLB%20ABS%20Optimal%20Challenge%20Strategy%20—%20產品規格書.md)。工作項目見 [Phase 2 地圖](../.scratch/phase2-models/map.md)。

## 資料來源與納入單位

Dataset A 是一般 MLB 歷史比賽，不是只含 Challenge 的 Dataset B。`download-historical-game` 保存一場官方 live feed 與同日完整 Statcast CSV，含來源 URL、查詢、UTC 下載時間、SHA-256、byte length、row count。當日其他比賽的 CSV 列不因被下載就自動納入；只有提供完整 feed 的場次會建置，其餘 game_pk 列於報告。

- 僅 MLB、例行賽、原訂九局制、Final 且有明確勝負的比賽。
- 排除七局制及提早結束的縮短比賽；不將它們當作九局制。
- feed 打席序號需連續，半局從一局上連續到真正終局。
- feed 的所有 `isPitch=true` 事件需與兩隊官方 `numberOfPitches` 終場計數一致；包含延長賽的總數只作完整性檢查。
- 第 1–9 局的 Statcast 三欄鍵必須與 feed 完全一致，缺球或多球整場排除；重複鍵直接報錯。
- feed 半局終點、逐局比分與終場比分需一致。逐球前比分不得倒退或超出原半局範圍。
- 壘包空值表示無人；缺欄是資料缺漏，不視為空壘。
- 無實際投球的打席不憑空生成逐球樣本；其數量保存於 `no_pitch_plate_appearances`。這會影響與其他 RE 定義的比較。

這是嚴格的首版建置規則，可能排除具有來源差異的真實比賽。後續擴大樣本時必須統計排除率與原因，不能只保留成功案例便宣稱全年完整。快照中的 Statcast 是否包含非實際投球 action、跨日補賽與 feed 修訂差異均需另行稽核。

## 特徵與標籤

[Savant 官方 CSV 說明](https://baseballsavant.mlb.com/csv-docs)將 `balls`、`strikes`、`outs_when_up`、壘上跑者及 `home_score`／`away_score` 定義為投球前狀態；`post_*_score` 是投球後比分，不能混用。

| Namespace | 內容及用途 |
|---|---|
| `pre_pitch_state` | 原始主客比分及既有 `GameState` 欄位 |
| `features` | 僅 `inning`、`half`、`outs`、`bases`、`balls`、`strikes`、`score_diff` |
| `labels.home_win` | 官方真正終場主隊勝負；可用未來結果作監督標籤，不可作 predictor |
| `labels.runs_to_half_end` | 原半局終場打方累計分數，減去投球前打方累計分數；含當球得分 |
| `sampling` | RE 完整半局資格與打席首球標記，不是 WP 特徵 |

球位、ABS 結果、observed WP、`delta_*`、球員 ID 與最終比分不會被複製到 `features`。Game/date/season/key 是資料分組與稽核欄位，不是模型輸入。本版尚未加入任何 Player Context。

## 時間切分與大比分

契約固定於 [config/phase2_dataset.json](../config/phase2_dataset.json)：

| 用途 | 年度 |
|---|---|
| Train | 2019、2021、2022、2023 |
| Validation | 2024 |
| Test | 2025 |
| External | 2026 |

2020 排除；2026 的 `823244`／`823569`／`825027` 另標為 `development_external`，不能作獨立外部成效證據。同一 game_pk 不得跨 split，重複 dataset 不可重複加權。契約不可透過命令參數靜默改成把 Test 放進 Train。

`score_diff = home_score - away_score`，不截尾、不把落後 8 分改為落後 5 分。資料報告按絕對分差 0–5／6–10／11+ 分列出投球數與比賽數；目前只是覆蓋統計，**不是已完成分組校準或可靠的大比分 WP**。未來 WP 模型還要檢查訓練支持範圍、各組 Brier／Log Loss、校準與以比賽為單位的信賴區間。

## RE24／RE288 的明確取樣規則

`estimate-re-development` 只使用 Train。輸入混有 Validation／Test／External 時，這些比賽不參與估計，報告列出忽略場次。沒有可用 Train 完整半局時拒絕輸出。

- RE24：每個打席的第一個實際觀測投球，依壘包 × 出局分成 24 格。遇到首球前自動好壞球時不強制首球 count 為 0–0。
- RE288：每次實際觀測投球，依壘包 × 出局 × 球數分成 288 格；相同球數因界外球重複出現時仍按投球次數計入，不假裝與打席加權相同。
- 每格輸出觀測數 `n`、場次 `games`、得分標籤總和 `run_sum` 及 `mean`。無觀測格子的平均為 null，不填零、不由官方表格代補。
- 僅打滿三出局的半局可作未截斷 RE。再見半局保留 WP 標籤，但整半局 RE 為 null，避免把因獲勝而提早終止視為「本來就不會再得分」。

排除再見半局仍可能造成選擇效應；正式 RE 必須增加前八局-only 敏感度分析，並與官方來源的年份、投球／打席加權及終局定義逐項比較。本版不提供統計信賴區間，也不宣稱已得到穩定的 league-average RE。

## 九局平手邊界

Train 中「九局下三出局時平手」的比賽，每場只計一次，以真正終場主隊勝負求平均。估計方式、允許年度、場次清單與來源 dataset hash 均保存；零場時為 null，不能默認 0.5。

這是版本化的開發估計，不讀延長賽 Game State 作 WP 特徵，也不建立延長賽 Challenge policy。正式採用前仍需檢查年度規則差異、樣本量與不確定性；不能將少量平手比賽的極端平均直接當作可靠邊界值。

## CLI 與可重播性

三個命令皆不覆寫既有輸出：

- `download-historical-game --game-pk ... --output ...`：需網路，保存完整來源 bundle。
- `build-historical-dataset --bundle ... [--bundle ...] --output ...`：離線重建，逐個重驗來源；同一完整 CSV 只按來源內容 hash 去重。
- `estimate-re-development --dataset ... [--dataset ...] --output ...`：離線 Train-only 開發估計。

資料建置 exit code 0 表示所選場次全數通過，不代表全季完整；1 表示有排除或沒有可用場次且已寫報告；2 表示輸入／來源／契約不合法。RE 命令 0 只代表開發估計完成，未觀測格可存在；2 表示無可用 Train 或輸入驗證失敗。

`dataset_content_sha256` 鎖定資料、契約與排除／覆蓋報告。runtime 與本機來源路徑不列入這個內容指紋，另外保存來源檔 hash 與程式檔 hash。完整檔案是否逐 byte 相同還取決於相同路徑與執行環境。這是意外變更檢查，不是數位簽章或來源真實性的密碼學認證。

## 正式實驗前仍需完成

1. 已於 2026-09-16 新增年度來源清冊、逐日快取／重試與跨年度小批次開發 lock；[批次結果](../reports/phase2_batch_validation.md)有 15 場通過、5 場非投球對齊待處理。完整球季逐球覆蓋與正式 dataset lock 仍未完成，不能把下載工程完成視為研究資料定稿。
2. 本專案 commit SHA 與可重現環境。使用者確認尚未設定 Git；沒有自行初始化、提交或重建。
3. Logistic Regression WP、Train 內時間隔離的校準、2024 選型、2025 鎖定後評估、2026 外部驗證。
4. 自建 WP 接回 S0／S1 與合成 Dynamic；官方共同範圍比較與大比分敏感度分析。
5. Dataset B 的 technical outage／post-replay-review 排除仍未完成，後續正式 policy 評估持續阻擋；Dataset A 工程進展不代表此限制已解決。

所有目前輸出維持 `formal_training_ready=false` 或 `formal_model_ready=false`，且 `formal_policy_evaluation_ready=false`。
