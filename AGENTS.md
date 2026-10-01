# AGENTS.md

## 語言規範

- 無論使用者以何種語言提出要求，所有回覆與溝通一律使用繁體中文。
- 新建立或更新的文件、規格、Issue、註解及其他文字內容一律使用繁體中文。
- 程式語法、識別字、API 名稱、CLI 指令、資料欄位及業界固定術語可保留英文。

## 專案狀態

這是既有且仍在進行中的研究專案。保留已完成的工作，並以增量方式擴充；不得重新初始化專案、刪除既有成果或重寫已完成的功能。

專案已於 2026-09-12 通過 **Phase 0 — Data Feasibility Gate（資料可行性閘門）**：2023–2025 Triple-A 與 2026 MLB 各 3 場 regulation-only 樣本通過 audit，61 次 attempts／30 次 overturned 與官方終場計數完全一致。2026-09-15 使用者同意 Phase 1 以官方 ±5 分覆蓋作限定原型驗收；三場／16 次挑戰仍保留 4 次缺值，不能改稱全數估值成功。目前進入 Phase 2，自建資料與 RE 開發估計不等於已完成 WP 訓練、校準、正式 Dynamic Policy 或 RRA。

## 目前研究方向（2026-10-01）

- 2026-10-01 最新主線決議：**停止開發未來「好挑戰機會」的機率／期望值模型及其正式動態政策**。歷史不利判決不等於值得挑戰的球；未挑戰球缺少可靠翻判標籤與球員決策時私有線索，全部算入會膨脹額度價值。主要交付限於已可挑戰的眼前情境：官方 S0／S1 WP、輔助 RE、假設翻判 WP 差，以及明示人工失敗額度成本下的條件式把握門檻。成本不是估計值，門檻不是正式 RRA 或無條件建議。Issue 03／04／05 的正式未來模型及 Issue 07 未完成部分移為延伸研究；既有成果保留作歷史證據。見 `reports/archive/phase3/phase3_scope_decision_2026-10-01.md`。本條優先於下方各日期舊計畫。

- 2026-10-01 Issue 07 第一輪[決策時資訊與歷史後續機會稽核](reports/archive/phase3/phase3_decision_time_feasibility_2026-10-01.md)已完成：固定 91 場／13,132 筆有額度暫定不利判決全保留，11,060 筆雙側 WP 可估；12,995 筆在歷史球序中有下一次同隊不利判決，包含零額度潛在判決。這些不是「值得挑戰」或實際會翻判的球。假設翻判 `WP(S1)-WP(S0)` 可由當時狀態計算，但事後 ABS 正誤、實際挑戰、球位與行動後額度不得篩選或進入決策時模型。歷史路徑不等於改選行動後的反事實；正式 `V(S,c)`／RRA 仍未完成。見 `src/abs_challenge/decision_time_audit.py`。

- 2026-10-01 後續更正：瀏覽器介面已將官方 S0／S1 WP 與原半局 RE288 列為主要結果，不再把兩機會模型推導的單一門檻放在主卡片，也不依賴其受忽略的 JSON 才能啟動。現在只列 `config/phase3_win_decision_protocol.json` 預宣告的零／低／高額度成本**假設**及條件式門檻範圍；該範圍不是估計值、統計信賴區間或正式 RRA。舊模型與 25%／75% 對稱數值保留歷史診斷，不進即時介面。見 `reports/archive/phase3/phase3_option_value_redesign_plan_2026-10-01.md` 與 `.scratch/official-wp-policy/issues/07-option-value-redesign.md`。

- 2026-10-01 歷史兩機會近似：`src/abs_challenge/option_proxy.py` 只以 Train 43 場／6,297 個起點擬合局數×攻守的未來 1／2 個同隊不利判決到達率與可估 WP 價值，含零額度潛在判決；以同質兩機會樹近似剩 1／2 次的邊際成本。Test 的 1,579 筆可估候選在當下 `p=0.50`、未來 `p_f=0.50` 時有 1,229 筆條件式建議挑戰，350 筆保留；249 筆不支援。這只描述歷史**實際球序**下的舊假設結果，不是改選行動的因果轉移或正式最優政策，亦不再接入即時介面。見 `reports/archive/phase3/phase3_option_value_and_ui_2026-10-01.md`；來源及模型 JSON 受 `.gitignore` 排除。

- 2026-10-01 使用者再次確認研究核心：**給定已可挑戰的情況，依挑戰隊伍勝率影響決定現在使用或保留額度**。`src/abs_challenge/win_decision.py` 與 `config/phase3_win_decision_protocol.json` 已輸出官方 S0／S1 決策隊伍 WP、指定翻判率的立即預期增益、可承受失敗額度成本與條件式決策；固定 Test 1,579 筆可估候選於 `p=0.50` 的增益中位數 0.45 個百分點，小／大人工成本下建議挑戰 1,382／643 筆。合成每局未來模型降為次要敏感度，不得與官方 WP 混算為實證增勝。ABS 故障／replay 來源未知是候選母體外推限制，**不是已可挑戰情境決策公式的前置閘門**。見 `reports/archive/phase3/phase3_win_decision_primary_2026-10-01.md`。真實球員 `p`、增量額度成本與正式最優政策仍未識別。

- 2026-10-01 Phase 3 歷史路徑支持稽核：`src/abs_challenge/phase3_empirical_support.py` 將固定 91 場／13,132 筆候選與額度感知 episode 一對一核對；12,950 筆有下一同隊機會、50 筆實際行動後額度耗盡、132 筆九局設限。從表內起點出發，1,063 筆在後續同隊候選中曾越界再返回；此為重疊起點數，不是未來反事實機率。Test 實際挑戰僅 57／1,828 筆。所有候選來源資格仍未知，當前雙側 WP 缺值 2,072 筆；正式 Legal、反事實、表外 continuation、Policy Gate 保持 false。見 `reports/archive/phase3/phase3_empirical_path_support_2026-10-01.md`；完整 JSON 受 `.gitignore` 排除。

- 2026-10-01 Phase 3 第一輪合成九局模型：`src/abs_challenge/phase3_synthetic_policy.py` 以 `config/phase3_synthetic_policy.json` 的人工每局機會、WP 比例損失與未來翻判率，倒推 `V(S,0/1/2)`、假設式門檻，並於 91 場／13,132 筆候選比較永不挑戰、固定信心門檻與動態原型。Test 的 1,579 筆可估候選於當前 `p=0.50`，三情境的動態挑戰數為 1,521／1,095／772；不支援 249 筆另列。這是**WP-only 人工轉移**，不是經驗 Game State、正式 Dynamic Policy、球員 RRA 或增勝。所有 Legal／反事實／實證表外／正式 Policy Gate 保持 false。見 `reports/archive/phase3/phase3_synthetic_regulation_policy_2026-10-01.md` 與 `.scratch/official-wp-policy/issues/05-policy-evaluation.md`；本機完整 JSON 受 `.gitignore` 排除。

- 對外閱讀研究進度時，先使用 `reports/phase0_feasibility.md`、`reports/phase1_integrated.md`、`reports/phase2_integrated.md`、`reports/phase3_integrated.md` 四份主要入口；逐輪報告封存於 `reports/archive/` 作歷史證據，舊數字不得蓋過後續更正。Phase 2 整合報告末節的舊 Phase 3 動態計畫已被 2026-10-01 最新範圍決議取代。

- 2026-10-01 修訂後 Phase 2 限定收尾：固定 96 場中 91 場納入、5 場挑戰事件無法定位而整場排除；91 場中 7 場實際進入延長賽，但 13,132 筆主要候選全在第 1–9 局。所有主要候選的 ABS technical outage／post-replay 資格皆為 `unknown`，11,060 筆有雙側官方 WP。九局平手當前 S0／S1 直接終局邊界壓力測試只碰到名義 External 的 1 筆候選，人工主隊邊界 0.60／0.75 可翻轉其情境建議；不得外推為整體策略穩健。`reports/archive/phase2/official_wp_phase2_closeout_2026-10-01.md`、`config/phase2_closeout_protocol.json` 及 `.scratch/official-wp-policy/issues/06-phase2-closeout.md` 記錄收尾；可進入明示假設的 Phase 3 原型，但完整 Legal Opportunity、反事實轉移、實證表外 continuation、正式 Policy／RRA 均未過關。舊自建 WP Phase 2 仍暫緩。完整結果 JSON 受 `.gitignore` 排除。

- 2026-09-30 決策時情境原型：`src/abs_challenge/policy_scenarios.py` 已提供單一 Game State 與固定 Dataset B cohort 的共同比較介面；`config/policy_scenario_protocol.json` 明示人工成功率、失敗額度成本與成功後續位移，`config/policy_scenario_example_state.json` 提供可重播範例。91 場／13,132 筆暫定候選中 11,060 筆雙側官方 WP 可估，2,072 筆不支援。Test 在假設 `p=0.50` 時，小／大成本情境分別有 1,382／643 筆建議挑戰。這只是敏感度盤點；`post_action_budget`、實際挑戰、翻判結果與到達標籤不得進入決策介面。ABS outage／replay、未來反事實、表外 continuation 及正式 Policy／RRA 仍未完成。見 `reports/archive/phase3/policy_scenario_prototype_2026-09-30.md` 與 `.scratch/official-wp-policy/issues/05-policy-evaluation.md`。本機完整 JSON 受 `.gitignore` 排除，不得假設其他 clone 可重播 cohort。

- 2026-09-29 Dataset B 額度感知新版契約與重估：離線核對 91 場 feed、原候選指紋與 367 次挑戰的一對一事件鍵；前輪 6 筆候選序列無法判定者已由官方 feed 確認 5 失敗／1 成功。13,132 筆分為 50 筆當下額度耗盡、12,950 筆下一同隊機會已觀察、132 筆額度仍在的 regulation 設限。只在額度仍在的 13,082 筆估計事後條件到達 hazard，Train 擬合、Validation 選 alpha 400、Test／名義 External 評估；External 差異 CI 含零。`post_action_budget`／翻判結果為事後欄位，不可用作 decision-time predictor；此模型不是反事實轉移或正式策略。見 `reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md` 與 `config/dataset_b_resource_aware_protocol.json`。舊基線數值僅保留歷史紀錄。

- 2026-09-29 Dataset B 行動支持與設限更正：舊基線把 182 筆無下一同隊有額度候選全標作 `regulation_end`；後續零額度候選先證明其中至少 45 筆已額度耗盡，另 6 筆當時只靠候選序列無法區分（已由上方新版契約解出）。舊 hazard／NLL／Brier 與九局設限敏感度僅保留歷史紀錄，不可作已校正到達模型或正式策略輸入。Train 12 個局數階段×攻守×額度格中僅 2 格達最低行動支持；`historical_action_overlap_gate_pass=false`、`arrival_baseline_censoring_contract_valid=false`、`counterfactual_transition_ready=false`。見 `reports/archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md` 與 `config/dataset_b_action_support_protocol.json`。

- 2026-09-29 Dataset B 更新：原 11 場官方 Challenge 計數不符中，6 場以 Savant ABS-only、完整逐球嚴格對齊與官方分隊成功／失敗計數唯一復原；5 場缺球無法定位，整場排除且不替補。固定 96 場中 91 場／13,132 筆有額度暫定風險集候選，模型輸入限定閘門通過；到達目標只計同隊下一個風險集候選，不計零額度或位置球員投手。ABS outage／replay 資格、正式 Legal population／holdout／Dynamic Policy 仍未完成。見 `reports/archive/phase2/dataset_b_challenge_recovery_2026-09-29.md`、`config/dataset_b_model_input_policy.json`。舊 9/24 數字保留歷史語境。

- 2026-09-29 Dataset B 到達基線第一輪已完成：僅 Train 擬合整體幾何離散 hazard 與球數×挑戰餘額收縮分層 hazard；Validation 選模、Test／名義 External 評估，右設限納入 likelihood。結果見 `reports/archive/phase2/dataset_b_observational_baseline_2026-09-29.md` 與 `config/dataset_b_baseline_protocol.json`。這是歷史路徑的觀察性模型；缺漏選樣／遊戲階段設限敏感度、正式 Legal 機會、行動依賴反事實、Dynamic Policy、RRA 仍未完成。本機結果及候選資料受 `.gitignore` 排除。

- 2026-09-29 Dataset B 同階段延伸：已分析五場 Train 缺漏的假設性情境、九局右設限，並以 Train／Validation／Test／名義 External 評估下一個已觀察機會的進攻／防守方及 WP 價值類別分布；可查 WP 下一事件的 Test／External 中位差值皆為 0.009，表外支援缺口另列。見 `reports/archive/phase2/dataset_b_followup_sensitivity_2026-09-29.md` 與 `config/dataset_b_followup_protocol.json`。五場情境不是復原或偏差界限，方向／價值分布只條件於歷史觀察到達；完整下一 Game State、行動依賴反事實與正式策略仍未完成。

- 2026-09-24 Dataset B 訓練前準備：96 場候選 feed 均取得，85 場完整逐球對齊，產出 13,252 個暫定候選與同隊下一候選的觀察性到達間隔／右設限；11 場官方終場挑戰計數不符保留失敗，不補樣。technical outage／replay 資格仍未知、正式 holdout 與訓練 readiness 均 false。見 `reports/archive/phase2/dataset_b_pretraining_preparation_2026-09-24.md`；本機來源及候選檔受 `.gitignore` 排除。
- 2026-09-24 Dataset B 已用固定 seed／配額及五份官方賽程 metadata 鎖定 96 個候選 `game_pk`；與 39 場已知開發樣本無交集，離線重播指紋一致。這只是賽程候選，逐場兩次制、實際 regulation-only、來源資格與正式 holdout 均未驗收；`formal_model_evaluation_ready=false`。見 `config/dataset_b_sampling.json` 與 `reports/archive/phase2/dataset_b_schedule_lock_2026-09-24.md`。本機來源快取與清冊受 `.gitignore` 排除。

- 2026-09-24 Dataset B 前置閘門：24／24 場 feed 的來源線索已離線盤點（78 個 `MJ`，無可證明全場可用的區間欄位），2,751 個候選的 ABS 技術可用性與 replay 後資格都保留 `unknown`。兩次制的 Train／Validation／Test／External 時間窗已預宣告，39 場已知開發場列入排除；新 game_pk、樣本量與完整開發清冊仍未鎖定，正式 holdout／模型 readiness=false。見 `reports/archive/phase2/dataset_b_readiness_2026-09-24.md`、`config/dataset_b_split_plan.json` 及本機 `data/processed/wp_expansion_acquisition_2026-09-24-v11.json`。

- 2026-09-24 已新增合成有限視野跨界契約：表外→表內路徑與機率質量保留；表外未解終點必須明示區間，勝負終局及九局平手走獨立規則；挑戰額度與區間敏感度測試通過。這不是由歷史資料估計的 Future Opportunity Model，也不代表正式 continuation、Dynamic Policy 或 RRA 完成。見 `reports/archive/phase2/official_wp_continuation_contract.md` 與 `.scratch/official-wp-policy/issues/03-continuation.md`。

- 2026-09-24 跨年度擴大樣本：官方 feed 24/24 場、完整逐球 CSV 9/9 日、ABS-only CSV 9/9 日已取得，且以 `--offline` 成功重播。選定場 regime 確認為 2024 IL 兩次、2025 IL 兩次、2025 PCL 三次、2026 MLB 兩次。18 場主要 cohort 現均完成 provisional opportunity 對齊；780464 打席 53 的 `AB` 打者逾時自動好球在嚴格結構化證據核對後視為非投球，原先成功 17 場逐場結果未變。2,489 個有額度暫定機會中 2,218 個兩側有 WP（89.11%），另 262 個零額度候選分列；2024 IL 829／937、2025 IL 702／834、2026 MLB 687／718 的分組支持已輸出。v9 另保留 289 筆未雙側估值候選的事件鍵與 S0／S1 結構化原因；有額度的 286 個不可查分支皆為轉移後分差超 ±5，另 127 個非純判決候選未進查表。這不是全季率或 legal population 完成。2024 AAA ABS-only CSV 無資料列；824087 的三鍵 challenge pitch 對應被同打席自動好球事件偏移，但 historical event alignment 成功。完整 Legal population 保持 provisional，正式策略 readiness=false。詳見 `reports/archive/phase2/official_wp_cross_year_sampling_plan.md` 與本機執行結果 `data/processed/wp_expansion_acquisition_2026-09-24-v9.json`；舊版 v6／v7／v8 保留為歷史證據。

- 2026-09-22 更新：五球終局三振的逐球 count.outs 延遲，已以打席出局數與同事件打者 outNumber 嚴格交叉驗證修正；actual attempts 為 22／29。完整六場 1,876 球對齊通過，962 個暫定機會中 706 個兩側支援、80 個零額度候選另留。214 項測試通過、離線重播一致。六場全部是開發資料，非獨立 external test；跨年度、代表性抽樣及資格來源限制尚未完成。見 `reports/archive/phase2/official_wp_opportunity_coverage.md`。下項保留前輪歷史紀錄。

- 官方 WP Issue 01 第一輪已檢查六場本機 2026 MLB 開發樣本：29 次 regulation attempts 中 17 次雙側支援、7 次雙側超界、5 次純判決出局數不符；另排除 3 次延長賽。208 項測試通過、離線重播一致。這不是全部機會覆蓋率；完整逐球來源、機會母體與跨年度驗證尚未完成，Issue 維持 claimed。見 `reports/archive/phase2/official_wp_coverage_development.md`。

- 2026-09-21 決策：主要研究改用固定官方 WP／RE288，自建 WP 與全季 Dataset A 擴充改列延伸研究並暫緩。既有成果與資料契約保留；不截尾真實分差，不宣稱正式 Dynamic Policy／RRA 已完成。
- 主要工作地圖為 `.scratch/official-wp-policy/map.md`；原 Phase 2 自建模型 Issue 未完成者暫緩，不自動續跑全季下載、壓縮或訓練。
- 當前兩個反事實可估值與未來動態分支可求值分開驗收。跨出 ±5 不得靜默截尾、丟棄路徑或假設必勝／必敗；RE288 不受相同分差欄位限制。
- 官方快照來源涵蓋至 2025 的宣告不等於本專案 Train／Test 切分；不可稱 2025 為官方 WP 獨立 holdout。下列 Dataset A 切分及自建模型要求保留供延伸研究。

## 開始工作前必讀

進行實質變更前，先閱讀與任務相關的下列文件：

- `README.md`
- `docs/official_wp_policy.md`、`docs/adr/0002-official-wp-primary.md`、`.scratch/official-wp-policy/map.md`（主線規劃與策略工作）
- `MLB ABS Optimal Challenge Strategy — 產品規格書.md`
- `reports/phase0_feasibility.md`
- `docs/data_dictionary.md`
- `docs/evaluation_design.md`
- `config/rule_regimes.json`
- `config/phase0_gate.json`
- `CONTEXT.md`（若存在）
- `docs/adr/` 下與任務相關的 ADR（若存在）
- `.scratch/phase0-hardening/map.md`（處理 Phase 0 時）
- `docs/phase2_dataset.md`、`config/phase2_dataset.json`、`.scratch/phase2-models/map.md`（處理 Phase 2 時）

## 重要實作脈絡

- Challenge 翻判成功時，MLB live feed 儲存的是 ABS 修正後判決；原始裁判判決為其相反結果。
- 部分 Triple-A 終局打席的 Challenge 僅出現在 plate-appearance result description，沒有逐球 `reviewDetails`。
- Stats API 與 Savant 的串接鍵為 `game_pk`、Savant 的一基底打席編號（`at_bat_index + 1`）及 `pitch_number`。
- 上述三欄鍵不可無條件外推到所有歷史投球：Dataset A v2 使用獨立的 `historical_alignment.py`，依完整打席事件、判決碼、前後球數、出局及跑者狀態對齊，保留兩套原始投球編號。`no_pitch` 只存對齊證據，不進投球／RE 樣本；未知判決碼、缺漏或歧義仍整場排除，不得只刪自動判決列或硬套固定編號偏移。
- Phase 2 Issue 06 已於 2026-09-18 完成固定樣本驗證：20 場／5,748 球通過，原先 15 場特徵與標籤未變；10 筆非投球事件排除、14 球跨來源編號不同。這不是全季覆蓋或 WP 模型完成。兩場九局平手的開發邊界平均為 1.0，樣本不足，不得作正式邊界值。
- 2026-09-19 Issue 07 已補齊 pitchout／missed_bunt 與明確 N 型 feed-only 非投球。同一跨月份 84 場／24,448 球通過，原 70 場資料指紋不變。N 事件另存 `alignment.feed_only_events`，仍重建跑壘、不進 CSV 自動判決計數／投球／RE。九局平手 9 場、主隊勝 6 場仍不作正式邊界；全季與 WP 未完成。兩個原固定空日期使批次 exit code 1，不代表 84 場有失敗。
- 歷史資料可能缺少挑戰者身分。應保留缺失狀態，不得自行推定 pitcher 或 catcher。
- 核心研究的決策單位是 Decision Team；守方已知但 pitcher／catcher 無法細分時可進入 team-level Gate，精確角色只供次要行為分析。
- `config/rule_regimes.json` 中 2023／2024 年 6 月 25 日前仍需逐場 format 證據；官方 feed 實際出現 `reviewType=MJ` 時只確認該場，沒有事件證據時人工 `--abs-format` 不得把狀態升級為 confirmed。2025 Triple-A 按聯盟拆分：IL 兩次、PCL 三次。
- `phase0_game_pass` 只是單場結果；只有跨年度 `phase0_gate_pass` 才授權進入 Phase 1。
- 單場有 `gameData.absChallenges` 時，逐球 attempts／overturned 必須與官方終場 counter 完全一致；`official_counter_pass = false` 一律阻擋單場 Gate。
- `pitch_observation`、翻判結果與 `delta_*` 是 label／事後資料，不得加入 decision-time model features。
- 主要研究範圍只含第 1–9 局；延長賽解析屬工程防呆，延長賽 Challenge policy 是 MVP 後的 extension。
- 九局平手使用明確版本化的 Regulation Boundary Value，不得直接視為比賽結束。
- Legal Opportunity 的 ABS technical outage 與 post-replay-review 排除仍未完成，schema 必須維持 `provisional_source_limitations`，不得把 Phase 0 pass 說成完整研究資料已定稿。
- 正式模型實驗必須記錄實際執行版本的 commit SHA 與工作目錄狀態。使用者於 2026-09-16 授權建立 Git 版本紀錄並推送至 `channychanny/MLB-ABS-Optimal-Challenge-Strategy`；本機沿用遠端 `main` 歷史，不得重建或強制覆寫。既有未記錄 commit 的開發產物不得追溯宣稱為正式實驗；後續提交與推送仍依各次任務授權。
- 下載及產生的資料集受 `.gitignore` 排除；不得假設每個 clone 都有本機樣本資料。
- Dataset A 使用完整 MLB 一般投球，不限 ABS Attempts；Train 2019／2021–2023、Validation 2024、Test 2025、External 2026，同場不可跨 split。RE 與九局平手邊界只 fit Train。
- 自建模型保留真實分差，不截成 ±5；分差 0–5／6–10／11+ 分別報告樣本支持。缺乏資料不能宣稱已可靠覆蓋。
- RE 開發版只納入滿三出局的半局；再見半局仍有 WP 勝負標籤，但 RE 為 null。空 RE 格子不得填零。校準與正式 WP 評估尚未實作。

## 驗證

在專案根目錄執行標準函式庫測試：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Agent skills

### Issue tracker

Issue 與規格以本機 Markdown 檔案追蹤，存放於 `.scratch/`。詳見 `docs/agents/issue-tracker.md`。

### Domain docs

本專案採用 single-context 配置：根目錄使用 `CONTEXT.md`，ADR 存放於 `docs/adr/`。詳見 `docs/agents/domain.md`。
