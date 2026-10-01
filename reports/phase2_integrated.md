# Phase 2 整合報告：資料、官方 WP 支援性與策略建模準備

**後續範圍決議（2026-10-01）：**本報告末節的 Phase 3 動態模型規劃屬當時版本，已完成的合成原型仍保留，但不再建立未來「值得挑戰」機會的機率／期望值模型。現行主線改為眼前已可挑戰情境的條件式 WP／RE 決策，見[Phase 3 整合報告](phase3_integrated.md)。

更新：2026-10-01。這份文件是 Phase 2 的單一閱讀入口；下列逐次報告保留原始時間點、指紋、失敗及修正證據，不刪除、不把舊數字倒改成新數字。Phase 1 的完成範圍見[Phase 1 整合報告](phase1_integrated.md)。

## 先釐清兩條 Phase 2 工作線

2026-09-21 依[ADR-0002](../docs/adr/0002-official-wp-primary.md)調整主線：研究重點是「何時使用兩次 ABS Challenge」，不是自行重建 WP。因此**舊 Phase 2：全季 Dataset A、自建 WP 訓練與校準**移為延伸研究並暫緩；其已完成資料工程仍保留。**修訂後 Phase 2：固定官方 WP 的支援性、Dataset B 候選母體、來源限制及九局內策略資料準備**是目前主線。兩者不能相加後說「自建 WP 已完成」，也不能把限定原型視為正式政策驗收。

本研究的主要決策只到第 9 局；來源比賽若進入延長賽，完整 feed 仍保存供官方終場計數稽核，但第十局以後的候選與補充額度不進主要策略模型。九局平手使用明示的外生 boundary，不研究延長賽何時挑戰。

## A. 保留的舊 Phase 2：Dataset A 與 RE 開發

| 時點與證據 | 已做到 | 不可推論為 |
| --- | --- | --- |
| [第一個小樣本](archive/phase2/phase2_progress.md) | 2019 真實一場／283 球完成來源核對，含 34 球絕對分差 6–10；Train-only RE 建置流程跑通 | 全季 RE、校準後 WP |
| [固定跨年度批次](archive/phase2/phase2_batch_validation.md) | 起初 20 場中 15 場／4,303 球通過；5 場非投球與編號偏移保守排除 | 五場沒有資料、可直接刪自動判決列 |
| [非投球對齊修正](archive/phase2/phase2_alignment_validation.md) | 同 20 場全數通過／5,748 球；10 筆非投球另存證據、14 球保留跨來源不同編號 | 任意歷史投球皆可固定三鍵對齊 |
| [跨月份擴大](archive/phase2/phase2_expanded_coverage.md)及[後續修正](archive/phase2/phase2_issue07_validation.md) | 固定 84 場由 70／20,234 球提升至 84／24,448 球；原 70 場資料指紋不變。Train RE288 有觀測 282／288 格，空格仍為 null | 全季覆蓋、稀有狀態可靠、自建 WP 已訓練 |
| [全季計畫與首月](archive/phase2/phase2_season_acquisition.md) | 固定五年度 12,029 場清冊；2019-03 的 54 場／15,627 球通過且可離線重播 | 全 12,029 場已取得或正式資料版本已鎖 |

舊工作線的 Train 為 2019／2021–2023、Validation 2024、Test 2025、External 2026。自建 WP、全季下載、壓縮儲存及 WP 整合均[暫緩](../.scratch/phase2-models/map.md)；這個切分**不是**固定官方 WP 的訓練／測試設計。九局平手的小樣本歷史均值（如 9 場中主隊勝 6 場）不取代固定官方 0.5 邊界。以上保留為可復用的工程成果，非目前主線的前置阻擋。

## B. 修訂後主線：官方 WP 與 Dataset B

| 工作與最新證據 | 目前結論 |
| --- | --- |
| [六場完整逐球先導](archive/phase2/official_wp_opportunity_coverage.md) | 1,876 球對齊；29 次第 1–9 局 actual attempts 中 22 次雙側 WP 支援、7 次超界。962 個有額度暫定機會中 706 次雙側支援；3 次延長賽挑戰另列。第一輪的 17／29 已被終局三振出局數延遲修正，不再當最新值。 |
| [24 場跨年度工程 cohort](archive/phase2/official_wp_cross_year_sampling_plan.md) | 其中 18 場兩次制主 cohort 均完成暫定機會對齊；2,218／2,489 有額度候選雙側 WP 支援（89.11%），262 個零額度候選另列。2025 PCL 三次制只作工程對照，不混入兩次制主母體。此比例不是全季率。 |
| [資格與時間切分](archive/phase2/dataset_b_readiness_2026-09-24.md)、[賽程鎖定](archive/phase2/dataset_b_schedule_lock_2026-09-24.md) | 先宣告兩次制時間窗與 39 場已知開發排除；依固定規則選 96 場，沒有依挑戰或 WP 結果補樣。完整開發清冊與正式 holdout 仍未驗收。 |
| [固定 96 場逐球準備及復原](archive/phase2/dataset_b_challenge_recovery_2026-09-29.md) | 85 場原樣通過、6 場以 ABS-only／feed／官方計數唯一復原，5 場缺球無法定位而整場排除；91 場形成 13,132 筆第 1–9 局、有額度且非明確野手投球的暫定候選。零額度及野手投球另列，不混入風險集。 |
| [行動支持與設限稽核](archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md)、[額度感知更正](archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md) | 舊到達基線將額度耗盡混作九局設限，其 hazard／NLL／Brier 只留歷史紀錄。新版經官方 feed 核對，13,132 筆分為 50 筆當下額度耗盡、12,950 筆下一同隊有額度候選已觀察、132 筆額度仍在時九局設限；後兩類 13,082 筆用於**行動後條件**到達模型。Train 12 個粗粒度行動支持格僅 2 格達最低門檻，不能識別反事實策略效果。 |
| [下一機會描述](archive/phase2/dataset_b_followup_sensitivity_2026-09-29.md) | 已觀察到達後的方向與 WP 價值類別、五場 Train 缺漏假設情境皆已盤點；舊九局設限敏感度受後續更正影響，不可當校正後 hazard。沒有完整下一 Game State 的行動依賴轉移。 |
| [合成跨界契約](archive/phase2/official_wp_continuation_contract.md)、[決策時情境原型](archive/phase3/policy_scenario_prototype_2026-09-30.md) | 表外→表內、未知區間、額度及九局平手的工程契約通過。91 場中 11,060／13,132 筆雙側 WP 可估、2,072 筆不支援；人工成功率／未來成本下可比較「挑戰或保留」，但不是真實 RRA 或最佳政策。 |

額度感知模型已按 Train 擬合、Validation 選參、Test／名義 External 評估，但使用 `post_action_budget`；它是**歷史行動和結果發生後**的條件分布，不能在球員決定是否挑戰前當成輸入。2025 Test 可檢查 Dataset B 時間泛化，卻不是官方 WP 快照完全獨立的測試。實際翻判結果、事後投球位置與觀察到的後續球序均不得洩漏到決策時特徵。

## Phase 2 收尾判定（2026-10-01）

以[可重播收尾驗收](archive/phase2/official_wp_phase2_closeout_2026-10-01.md)核對固定選樣、候選檔、官方估值及邊界。固定 96 場中 91 場納入、5 場整場排除且不替補；91 場中 7 場雖實際進入延長賽，**全部 13,132 筆主要候選仍在第 1–9 局**。11,060 筆雙側 WP 可估，2,072 筆保留不支援。所有 13,132 筆的 ABS 技術停用與 replay 後資格皆為 `unknown`，不得稱完整 Legal Opportunity。

官方九局平手主隊 boundary 為 0.5；另用人工 0.25／0.40／0.60／0.75 作直接終局 S0／S1 壓力測試。只有名義 External 的 1 筆當下候選直接接到平手終點，其情境建議在 0.60／0.75 時翻轉。這**不是**將邊界變化沿較早局數未來路徑傳遞的全政策敏感度，也不是人工格點的可信區間。

因此判定為：**限定的 Phase 2 資料與原型證據包已收尾，可開始明示假設的 Phase 3 原型；正式 Phase 2／Policy Gate 未通過。** `formal_legal_opportunity_ready=false`、`counterfactual_transition_ready=false`、`formal_policy_evaluation_ready=false`。完整來源資格、開發清冊、未來表外 continuation、行動依賴轉移與政策樣本外績效仍待處理，不能因進入下一階段而自動改成完成。

## Phase 3 的下一步

1. **先固定九局內模型契約。** 決策時只讀判決前 Game State、原判、Decision Team、剩餘額度與官方 S0／S1；指定人工翻判成功率／對手策略的版本化情境，明列未知 Legal 資格和不支援的分支，不從 367 次歷史挑戰推估全部機會的成功率。
2. **建立行動分支的有限策略原型。** `save` 保留當下額度，`challenge` 成功保留、失敗扣一；以明示假設描述後續機會、狀態與九局終點。表外路徑可回表；無證據的表外終點回傳區間或「無法判定」，不截成 ±5、不把觀察到的球序假裝為替代行動後的球序。
3. **用同一固定母體比較並做壓力測試。** 比較不挑戰、明示固定門檻及動態原型，按剩 1／2 次、攻守方、局數與 WP 支援分組；對成功率、未來額度價值、九局平手及表外區間做敏感度。先報告假設下建議是否翻轉、覆蓋與不可判定比例，不宣稱實際增加勝場。正式 RRA、`V(S,0/1/2)`、政策增勝及不確定性評估須待來源與反事實閘門過關。

本階段仍不研究延長賽挑戰策略，也不恢復自建 WP 全季下載。上述報告中的本機來源、候選檔與完整 JSON 多受 `.gitignore` 排除；其他 clone 不會自動重現數字。正式實驗需另記錄乾淨或明確鎖定的執行版本及來源指紋。

2026-10-01 後續：上述前三項已先以**人工機會機率與 WP 尺度狀態**完成第一輪九局倒推及固定樣本盤點，詳見[Phase 3 第一輪報告](archive/phase3/phase3_synthetic_regulation_policy_2026-10-01.md)。這是有限原型，不是後續 Game State 分布已從資料估得；完整表外質量與正式政策績效仍未完成。
