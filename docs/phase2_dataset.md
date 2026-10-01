# Phase 2：Dataset A 與 RE 開發契約

> 2026-09-21 決策：主要研究改用固定官方 WP／RE288，自建 WP 與全季 Dataset A 擴充改列延伸研究並暫緩。既有成果與資料契約保留；不截尾真實分差，不宣稱正式 Dynamic Policy／RRA 已完成。 本文件以下內容描述保留的工程契約與延伸研究重啟條件，不表示仍需先完成自建 WP 才能推進主線。見 [官方 WP 主線](official_wp_policy.md)。

## 目前階段

Phase 1 已由使用者同意以官方 ±5 分範圍限定驗收。Phase 2 第一個工作切片實作了來源快照、歷史狀態／標籤、年度切分與 RE 開發估計；**WP 訓練、校準與替換估值來源尚未完成**。

規格入口：[產品規格第 30 節](../MLB%20ABS%20Optimal%20Challenge%20Strategy%20—%20產品規格書.md)。工作項目見 [Phase 2 地圖](../.scratch/phase2-models/map.md)。

## 資料來源與納入單位

Dataset A 是一般 MLB 歷史比賽，不是只含 Challenge 的 Dataset B。`download-historical-game` 保存一場官方 live feed 與同日完整 Statcast CSV，含來源 URL、查詢、UTC 下載時間、SHA-256、byte length、row count。當日其他比賽的 CSV 列不因被下載就自動納入；只有提供完整 feed 的場次會建置，其餘 game_pk 列於報告。

- 僅 MLB、例行賽、原訂九局制、Final 且有明確勝負的比賽。
- 排除七局制及提早結束的縮短比賽；不將它們當作九局制。
- feed 打席序號需連續，半局從一局上連續到真正終局。
- feed 的所有 `isPitch=true` 事件需與兩隊官方 `numberOfPitches` 終場計數一致；包含延長賽的總數只作完整性檢查。
- 第 1–9 局先經 v2 事件對齊；Statcast 事件需完整對應 feed 的實際投球與已支援的 `no_pitch`。留下的實際投球鍵與官方 feed 完全一致，缺漏或多出事件整場排除；原始重複鍵直接報錯。
- feed 半局終點、逐局比分與終場比分需一致。逐球前比分不得倒退或超出原半局範圍。
- 壘包空值表示無人；缺欄是資料缺漏，不視為空壘。
- 無實際投球的打席不憑空生成逐球樣本；其數量保存於 `no_pitch_plate_appearances`。這會影響與其他 RE 定義的比較。

這是保守建置規則，可能排除具有未支援來源差異的真實比賽。後續擴大樣本時必須統計排除率與原因，不能只保留成功案例便宣稱全年完整。跨日補賽與 feed 修訂差異仍需另行稽核。

## 歷史事件對齊 v2

Dataset schema 為 `historical-dataset-a-v2`，對齊器為 `historical-event-alignment-v1`。舊 v1 仍可驗證與重算開發 RE，用於修正前後比較；沒有對齊證據的舊資料不會自動升級成 v2。

- 依打席事件順序核對，Statcast 編號須從 1 連續，feed 事件 index 須完整。`isPitch=true` 與已支援的自動好壞球須一對一匹配；明確 N 型 feed-only 非投球不要求 CSV 列。不能只依列數或固定編號偏移。
- 同時檢查兩來源判決類型、前後球數、半局、事件前出局數及三壘跑者 ID。壘位由半局起點、runner movement 與代跑事件重建，再與打席終點的 `postOn*` 核對；不使用 Statcast 自己當驗證答案。
- 同一事件的分段跑壘只有在路徑唯一時合併；全空 runner 佔位列必須另有同跑者的實際移動證據才可忽略。第三出局後不延續壘包狀態。未支援判決碼、缺欄或矛盾均排除，不猜測。
- 來源判決碼採已驗證白名單。固定 feed 的觸身球 `H` 在來源計數上會令 `balls` 加一；這不是 ABS 判決，也不改變它屬實際投球的分類。新碼須先補來源證據與測試。
- 輸出 `pitch_number` 保留 Statcast 原值；`alignment.feed_pitch_number`、`alignment.statcast_pitch_number` 與 `alignment.feed_event_index` 保存兩來源鍵。另保存 `feed_call_code`、前後球數、事件前出局／壘位及跑者 ID，均為稽核證據，不加入 `features`。
- 非投球列存於 `games[].alignment.non_pitch_events`，不進 `rows`、RE24 或 RE288，也不是 ABS 可挑戰投球。`non_pitch_rows` 與 `renumbered_pitch_rows` 分別計數；無實際投球的整個打席不生成樣本。
- 2026-09-19 補齊 `P / pitchout`（來源壞球數加一）及 `M / missed_bunt`（好球數加一），均為實際投球。N 型 `no_pitch` 必須明確非投球、無 call／投球編號／投球資料、不改球數，出局旗標亦須與同事件跑者證據一致；跑壘仍由完整事件重建。
- N 型事件另存選用欄位 `games[].alignment.feed_only_events`，含原始事件 index、前後球數、事件前跑者／出局及出局旗標。不進 `non_pitch_rows`、投球或 RE；沒有這類事件時不新增空欄位，以保留既有資料內容。驗證器檢查重複事件、球數不變及壘包證據；未知型態與缺失實際投球仍排除。

固定 20 場核對結果與限制見 [事件對齊驗證報告](../reports/archive/phase2/phase2_alignment_validation.md)。Phase 0 的 Challenge 三欄 join 不變。

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

## 延伸研究重啟後的驗收條件

2026-09-19 Issue 07 已完成：同一 84 場／24,448 球全數通過，原 70 場完整資料指紋不變；192 項測試通過。開發 Train RE288 為 282／288 格有觀測，九局平手 9 場仍不足以採用正式邊界。最新證據見 [Issue 07 驗證](../reports/archive/phase2/phase2_issue07_validation.md)。

2026-09-18 後續擴大工程樣本已選定 84 場，70 場／20,234 球通過，14 場保留排除。新增 2 場真實再見，Train 九局平手共 8 場；Validation 尚無 11+ 分支持。這推進了下列第 1 項的小樣本覆蓋驗證，但全季與正式鎖定仍未完成。新來源差異追蹤於 Issue 07；詳見 [覆蓋報告](../reports/archive/phase2/phase2_expanded_coverage.md)。

1. 2026-09-18 的 v2 對齊讓同一固定 20 場／5,748 球全數通過；仍須驗證完整球季逐球覆蓋、排除率、真實再見與稀有狀態，並建立正式 dataset lock。不能把工程樣本成功視為研究資料定稿。
2. Git 基準已建立；本輪對齊修正仍是未提交的工作目錄。正式實驗需記錄實際使用版本、乾淨工作目錄及固定環境；不能拿基準 SHA 宣稱包含尚未提交的修正。
3. Logistic Regression WP、Train 內時間隔離的校準、2024 選型、2025 鎖定後評估、2026 外部驗證。
4. 自建 WP 接回 S0／S1 與合成 Dynamic；官方共同範圍比較與大比分敏感度分析。
5. Dataset B 的 technical outage／post-replay-review 排除仍未完成，後續正式 policy 評估持續阻擋；Dataset A 工程進展不代表此限制已解決。

所有目前輸出維持 `formal_training_ready=false` 或 `formal_model_ready=false`，且 `formal_policy_evaluation_ready=false`。
