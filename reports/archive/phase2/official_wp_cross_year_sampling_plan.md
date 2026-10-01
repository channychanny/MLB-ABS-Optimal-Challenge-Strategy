# 官方 WP 跨年度覆蓋：樣本清冊與來源限制盤點

日期：2026-09-23。本文先記錄樣本鎖定及來源限制；後續取得／分析結果附於文末更新段落。

## 目前已完成

固定 12 個日期分層，每層最多選 2 場，共 24 場；9 個官方賽程快照取得成功並重播。選場只看已終場、例行賽、排定九局、聯盟／賽事和 game_pk hash 排序；不使用 score、Challenge 次數、翻判結果、WP 或表格是否支援。所有符合資格場次和未抽中場次保存在本機快取 JSON。

清冊選場 SHA-256：`07012e576e2bdbf0d29e18c9f00d17478388b18aecbc6da855a70399a30a9191`。計畫檔 SHA-256 見 [選樣計畫](../config/official_wp_expansion.json) 的衍生 manifest，程式保存 runtime／來源 manifests。最多抽兩場是每一預定日期的工程樣本，不是每組兩場的母體隨機統計樣本；不把覆蓋比率解釋成聯盟全年發生率或信賴區間。

以下清冊欄位中的「尚未下載」是鎖定清冊建立時的狀態，並非目前進度；目前下載與分析結果以本報告文末的 2026-09-23 更新為準。

分層按 regime 控制樣本範圍：

- 2024-06-25 後 International League：每日期 2 次制。
- 2025 International League：2 次制。
- 2025 Pacific Coast League：3 次制，因此只作制度／資料工程對照，不能混入兩次制主估計。
- 2026 MLB：2 次制。仍須由逐場 feed 的 ABS 事件、比賽場地／例外資料確認實際格式；僅 schedule 隊伍 metadata 不足以確認 ABS 可用。

## 固定清冊

### aaa-2024-il-2024-07-20

資格賽數 7；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2024-07-20 | 752594 | 4a1dd18f8dcb | 尚未下載 feed／確認 ABS format |
| 2024-07-20 | 753574 | 6b673d72b7d8 | 尚未下載 feed／確認 ABS format |

### aaa-2024-il-2024-08-20

資格賽數 10；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2024-08-20 | 752664 | 1f5cefe48ac7 | 尚未下載 feed／確認 ABS format |
| 2024-08-20 | 752811 | 31409d9179e5 | 尚未下載 feed／確認 ABS format |

### aaa-2024-il-2024-09-10

資格賽數 9；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2024-09-10 | 753323 | 00c8b6822897 | 尚未下載 feed／確認 ABS format |
| 2024-09-10 | 753402 | 26851a5096d2 | 尚未下載 feed／確認 ABS format |

### aaa-2025-il-2025-05-20

資格賽數 6；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2025-05-20 | 780464 | 136b431dd8d8 | 尚未下載 feed／確認 ABS format |
| 2025-05-20 | 781135 | 49cfbba9eecc | 尚未下載 feed／確認 ABS format |

### aaa-2025-il-2025-07-20

資格賽數 9；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2025-07-20 | 781117 | 1106969c9e09 | 尚未下載 feed／確認 ABS format |
| 2025-07-20 | 781631 | 12dd46414147 | 尚未下載 feed／確認 ABS format |

### aaa-2025-il-2025-08-20

資格賽數 7；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2025-08-20 | 781705 | 35f761258155 | 尚未下載 feed／確認 ABS format |
| 2025-08-20 | 780878 | 481e76493227 | 尚未下載 feed／確認 ABS format |

### aaa-2025-pcl-2025-05-20

資格賽數 3；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2025-05-20 | 779937 | 37193bf65adf | 尚未下載 feed／確認 ABS format |
| 2025-05-20 | 780010 | 430801db3b56 | 尚未下載 feed／確認 ABS format |

### aaa-2025-pcl-2025-07-20

資格賽數 5；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2025-07-20 | 779615 | 190473d8ceee | 尚未下載 feed／確認 ABS format |
| 2025-07-20 | 780056 | 9e2f9f9da75b | 尚未下載 feed／確認 ABS format |

### aaa-2025-pcl-2025-08-20

資格賽數 4；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2025-08-20 | 780205 | 96cad5a0a404 | 尚未下載 feed／確認 ABS format |
| 2025-08-20 | 779754 | acc0ebe7a9c6 | 尚未下載 feed／確認 ABS format |

### mlb-2026-2026-05-20

資格賽數 15；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2026-05-20 | 824273 | 1c1208e86ce7 | 尚未下載 feed／確認 ABS format |
| 2026-05-20 | 823134 | 22f07b6ca404 | 尚未下載 feed／確認 ABS format |

### mlb-2026-2026-07-20

資格賽數 15；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2026-07-20 | 824087 | 0e71682ff65d | 尚未下載 feed／確認 ABS format |
| 2026-07-20 | 824167 | 1560bf692b58 | 尚未下載 feed／確認 ABS format |

### mlb-2026-2026-09-10

資格賽數 5；固定抽樣 2/2；落空 0。

| 日期 | game_pk | SHA-256 排序值前 12 碼 | 狀態 |
|---|---:|---|---|
| 2026-09-10 | 824872 | 36ce7d1dc40e | 尚未下載 feed／確認 ABS format |
| 2026-09-10 | 823088 | 9855c00e4669 | 尚未下載 feed／確認 ABS format |


## 官方資格規則與來源證據的界線

Baseball Savant 對 Challenge Opportunity 的公開定義要求被叫球、不利判決、至少一次剩餘額度，排除野手登板及 ABS technical issue。[官方指標文件](https://baseballsavant.mlb.com/abs-metrics-documentation)。MLB 2026 規則說明記載 replay review 後不能再提出 ABS Challenge，並解釋 replay-review 正在被詢問時如何與 ABS challenge 排序；它也說明技術故障可以讓 ABS 暫停，期間不接受 challenge。[MLB 2026 ABS 系統說明](https://www.mlb.com/news/abs-challenge-system-mlb-2026)。

但目前這些比賽／賽程資料欄位，尚無已驗證、涵蓋整場的 ABS unavailable interval 標記，亦無能證明「該球之前尚未發生 replay review」的可靠標記。因此：

- feed 找到 `reviewType=MJ` 只能證明該場曾使用 Challenge System，不能證明全場始終可用。
- 沒有 technical-error event 或 replay 字樣不代表沒有故障／replay；缺證據保留 `eligibility_unknown` 或來源限制。
- 每場必須重新核對 finalized official counter、挑戰 ledger、剩餘額度、format regime、場地和符合資格球員；format 不明、來源不全、counter 不符均保留為失敗／未知且留在流程分母。
- 法規文字可判定條件，不能替代事件時間戳資料。若公開資料無法重建 unavailable intervals／replay ordering，需縮小 estimand 為「資料可見的 provisional opportunities」，不能稱官方完整 Legal Opportunity population。

## 執行與驗收順序

1. 逐場取得固定清冊 feed，保存原 bytes／manifest；依規則與事件證據確認是否 Challenge System。
2. 取得固定 9 個日期的 MLB／Triple-A 完整 Statcast CSV，保存 URL、參數、時間、row count、byte length、SHA-256。
3. 以完整事件序列對齊 feed／CSV，核對出局、跑者、比分、總投球及 challenge counters。
4. 全部不利判決均輸出：挑戰額度、格式／技術／replay 資格狀態、actual attempt 標籤；事件來源未知不可 silently drop。
5. 分開報告 2024 IL 兩次、2025 IL 兩次、2025 PCL 三次（工程對照）、2026 MLB。兩次制主分析不得混入三次制度。
6. WP 以固定 v2 baseline 計算；unknown／unsupported／out-of-range 留在明確分母，RE-only 可保留，WP/RRA 不補值。
7. 六場舊開發樣本及這 24 場新 cohort 都登記為已參與開發，不作獨立外部測試。完成 coverage report 後再檢視其他年月是否需要第二批樣本。

目前 6 場開發樣本的 962 暫定機會／706 雙側支援仍只是前導工程結果。整體跨年 cohort 尚無機會分母、coverage estimate 或 official legal population pass；正式 policy readiness 維持 false。

## 2026-09-23：資料取得與逐球覆蓋初檢

依鎖定樣本完成官方 MLB Stats API feed 24/24 場、Baseball Savant 完整逐球 CSV 9/9 日期下載，共 36,274 列逐球資料；另取得 9 日期 ABS-only CSV。原始檔與來源 manifest 放在 gitignore 管理的 `data/raw/wp_expansion/`；manifest 記錄 URL、下載時間、列數、byte length 與 SHA-256。取得與分析腳本為 [`scripts/acquire_official_wp_expansion.py`](../scripts/acquire_official_wp_expansion.py)，可使用既有來源快取離線重播；機器可讀執行結果在 `data/processed/wp_expansion_acquisition_2026-09-23-v6.json`（本機忽略追蹤，不隨 Git clone 提供）。

逐場 regime 以 feed metadata 重新判定：2024 IL 六場兩次、2025 IL 六場兩次、2025 PCL 六場三次、2026 MLB 六場兩次。發現原 `config/rule_regimes.json` 將 2025 IL／PCL 合成兩次，已按聯盟拆開並補回 PCL 三次額度；PCL 六場僅作工程參照，不納入主要兩次額度機會分母。18 場主要 cohort 的官方 attempts 均與 feed counter 相符。使用 ABS-only CSV 做直接 State API／Savant 事件鍵 audit 時，主 cohort 為 11/18 通過；六場 2024 AAA ABS-only CSV 均只有標頭、沒有挑戰列，824087 另因同打席先發生自動好球而出現三鍵球數錯位。這些 audit 失敗不等同挑戰 counter 失配，狀態分開保留。整體 15/24 通過單場 Phase 0 audit；PCL 另有一場 ledger 失敗，兩種缺口都未隱去。

18 場主要 cohort 中，17 場成功完成整場事件序列對齊與暫定候選建構；一場（780464）因打席 53 的自動判決證據／球數變化不一致，整場拒絕、不部分刪列。17 場共 2,346 個有額度、投手資格已識別的暫定機會：2,156 個兩側可查 WP（91.90%）、2 個單側可查、63 個兩側均超官方範圍、125 個純判決不支援（含額外跑壘複合事件）。另保留 262 個零額度候選，其中 244 個兩側可查；零額度不併入有額度主要機會覆蓋率。這些都是樣本內工程覆蓋數，不是全季比例或效益估計。

另一場 2026 MLB（824087）的 8 次 attempts 官方總數吻合，但 feed 的打者逾時自動好球為非投球事件、接著才是被挑戰的第一實際球（feed pitch number 1；Savant ABS-only pitch number 2）。因此直接三鍵 join 找不到正確 Statcast 狀態；若用完整逐球檔不篩自動判決列，則可能錯把該 `automatic_strike` 列配給挑戰球。獨立完整事件序列對齊保留這個非投球偏移，仍涵蓋該場並核對 Challenge ledger 與相應判決／額度，因此暫列 17 場逐球母體中的一場，但保留該 audit 限制，不宣稱 Phase 0 gate 通過。PCL 的 780010 另有 ledger audit 失敗；PCL 不進主要估值。

### 來源與推論限制、下一步

- 本輪不是獨立測試或代表性抽樣；不可把 91.90% 外推至全季／未來比賽，也沒有訓練 WP 模型或完成動態策略。
- ABS outage 時段及 replay-review 後挑戰資格仍無逐球事件來源可核實，估值母體仍標為 `provisional_source_limitations`，不能稱完整 Legal Opportunity。
- 下一步先針對 780464 打席 53 找出自動判決對齊缺口，並釐清 824087 的三欄 count 差異與替代事件對齊證據；完成後重跑固定 lock，再檢查不同年度／聯盟的分組支持。正式 Dynamic Policy 之前仍須另完成跨 WP ±5 分的 continuation 設計與敏感度分析。

本輪以快取執行 `--offline` 重播成功，選樣 lock 未改；完整標準函式庫測試 221 項通過。`formal_policy_evaluation_ready` 維持 `false`。

## 2026-09-24：AB 自動好球對齊修正與固定樣本重播

780464 打席 53 的 feed 以 `no_pitch`／`AB` 記錄打者逾時自動第三好球；Savant 在同打席另有一列 `automatic_strike`，但它不是實際投球。對齊器現在僅在 feed 同時具有 `Automatic Strike - Batter Timeout Violation`、`violation.type=batter_timeout` 及一致的判決旗標、球數／出局／跑者狀態時接受 `AB`，並將該列留作非投球證據；缺少結構化證據仍整場排除。780464 因而有 285 顆實際投球、1 列非投球自動好球，沒有把第三好球誤算成投球或 RE 樣本。

使用未變的選樣、規則及官方 baseline SHA，以既有來源快取重跑 `--offline --output data/processed/wp_expansion_acquisition_2026-09-24-v7.json`。兩次制主要 cohort 的 18／18 場現可完成逐球對齊；先前成功的 17 場逐場投球數、候選數及 WP 支援分類均未變。780464 新增 143 個有額度暫定機會，其中 62 個 S0／S1 兩側可查、79 個兩側超出官方表格、2 個純判決不支援。這場使主要 cohort 的兩側覆蓋率由舊版 2,156／2,346（91.90%）更新為 **2,218／2,489（89.11%）**；另有 2 個單側、142 個兩側超界、127 個純判決不支援。262 個零額度候選仍另列，其中 244 個兩側可查；不能併入有額度分母。

三個兩次制 regime 各有 6 場完成對齊：2024 IL 有額度暫定機會 937 個、2025 IL 834 個、2026 MLB 718 個；這是鎖定工程 cohort 的數量，不代表年度或聯盟的正式涵蓋率。18 場官方 attempts 計數仍吻合，但 ABS-only 直接三鍵 audit、2024 AAA 空挑戰匯出及 824087 的自動好球位移限制未解除；15／24 單場 Phase 0 audit 通過數未變。ABS outage／replay 後資格尚缺逐球來源，因此 `legal_opportunity_status=provisional_source_limitations`、`formal_policy_evaluation_ready=false`。這 24 場及先導樣本均已參與開發，不得充當未見外部測試。標準函式庫測試 223 項通過；新 JSON 留在本機 gitignore 路徑，不隨 clone 提供。

進入 Phase 3 前，Phase 2 仍須完成或明確縮限資格母體、按候選狀態及 regime 報告覆蓋／缺值，鎖定跨 ±5 分的未來分支 continuation 與九局平手邊界敏感度，以及 Dataset B 的 game-level 時間切分與未見驗證清單。不能用本次對齊修正或 89.11% 單一數字取代這些閘門。

## 2026-09-24：有額度候選的分組覆蓋與缺值位置

新增 `candidate_grouped_support`，對每個候選母體分別依 `year`、`regime`、`game_pk`、`decision_side`、`inning`、真實 `score_diff` 及 `count` 列出分母、各狀態數與雙側支援率。零額度仍是獨立母體，沒有混入下表。使用相同鎖定來源離線重播至本機 `data/processed/wp_expansion_acquisition_2026-09-24-v8.json`；選樣 SHA、原始來源及主要總數與 v7 相同，只有新增的分組輸出。

| 兩次制度工程樣本 | 場數 | 有額度暫定候選 | S0／S1 雙側可查 | 雙側率 | 兩側不可查 | 複合事件不支援 | 單側可查 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 IL | 6 | 937 | 829 | 88.47% | 44 | 62 | 2 |
| 2025 IL | 6 | 834 | 702 | 84.17% | 98 | 34 | 0 |
| 2026 MLB | 6 | 718 | 687 | 95.68% | 0 | 31 | 0 |
| 合計 | 18 | 2,489 | 2,218 | 89.11% | 142 | 127 | 2 |

缺值高度集中，不能視為隨機散失：780464 一場為 62／143 雙側可查，79 個兩側不可查；2024 IL 的 753323 為 91／146、44 個兩側不可查。兩場共占 123／142 個兩側不可查。按真實投球前主隊分差，絕對值大於 5 的 150 個候選中有 142 個兩側不可查、6 個複合事件不支援、2 個單側可查；絕對值不超過 5 的候選沒有兩側不可查。按局數，兩側不可查的 142 個均在第 5–9 局。這些是狀態與結果的描述性關聯，不等於缺值原因已逐筆完成因果歸類，也不能從 18 場推論整季。

進攻方決策 719／778（92.42%）雙側可查；防守方 1,499／1,711（87.61%）。分組數量及全部 count、局數、分差格子可由 v8 JSON 重播檢查；較小格子不作效果推論。接下來應在 Issue 01 補上逐筆 S0／S1 缺值原因及邊界分類，並在 Issue 03 決定未來路徑超界時如何繼續求值；本分組結果沒有改變 `provisional_source_limitations` 或 `formal_policy_evaluation_ready=false`。

## 2026-09-24：逐筆 S0／S1 缺值原因

在同一固定來源再次以 `--offline --output data/processed/wp_expansion_acquisition_2026-09-24-v9.json` 重播。v9 增加 `candidate_missing_diagnostics`：每個未雙側估值候選保留 `game_pk`、打席、Savant 球號、feed 事件索引、母體、決策前分差／球數及 S0／S1 的支援旗標、轉移後真實分差、終局類型和結構化缺值碼。289 筆診斷事件鍵均唯一；有額度與零額度仍分開。v8／v9 的選樣 SHA、2,751 個總候選及所有既有支援分類不變。

| 母體 | 候選總數 | 未雙側估值候選 | 不可查的分支數與原因 | 尚未進行 S0／S1 查表 |
| --- | ---: | ---: | --- | --- |
| 有額度暫定機會 | 2,489 | 271 | 286 個分支皆為轉移後主隊分差超出 ±5；來自 142 個雙側及 2 個單側候選 | 127 個非純判決／同球額外事件 |
| 零額度候選 | 262 | 18 | 0 | 18 個非純判決／同球額外事件 |

兩個單側案例都在 753323：S0 的轉移後主隊分差為 +7、表格不可查；S1 是合法的 `home_win` 終局，依規則給勝率 1。因此不應把終局側誤報為表格涵蓋，也不能把 S0 的 +7 截成 +5。127 個有額度的查表前排除中，79 個 feed 判決描述不是單純 `Ball`／`Called Strike`，48 個有非單純保送強迫進壘／三振的跑壘事件；`unsupported_compound_event` 狀態名稱涵蓋這兩類，並不表示每筆都已證實是額外跑壘。這些仍留在有額度分母，未補造反事實值。

結構化碼依轉移後狀態判定，而非從錯誤文字猜測；完整官方表格下目前只觀察到 `score_diff_out_of_range`。報告尚未證明未來路徑可求值、ABS outage／replay 資格或全季支援率；正式策略 readiness 仍為 false。標準函式庫測試 225 項通過，v9 JSON 為本機 gitignore 產物。

## 2026-09-24：來源資格未知與 Dataset B 切分預備

同一鎖定 cohort 的 v11 離線重播逐場加入 feed 來源訊號盤點；24 場均有來源檢查，78 個 `MJ` review 只證明個別挑戰事件，沒有建立全場停用區間或逐球 replay ordering。2,751 個候選的技術可用性及 replay 後資格均保留 `unknown`，原 WP 支援總數不變。Dataset B 時間窗與 39 場已知開發排除清冊已預宣告；尚未選定新場次或完成獨立 holdout。詳見[資格與切分預備報告](dataset_b_readiness_2026-09-24.md)。
