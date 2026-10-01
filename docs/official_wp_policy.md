# 官方 WP 主線與研究驗收契約

更新：2026-09-21。依 [ADR-0002](adr/0002-official-wp-primary.md)，本文件定義調整後的主要研究範圍；歷史 Phase 1／Phase 2 報告仍保留原執行時的事實。

**2026-10-01 後續範圍決議優先適用：**未來不利判決的到達率不能代表未來「值得挑戰」機會，未挑戰球沒有可靠的翻判標籤與球員當時私有判斷。因此主線不再估未來好挑戰機會的機率／期望值，不繼續正式 Future Opportunity、`V(S,c)`、Dynamic Policy 或 RRA。現行研究限於給定眼前已可挑戰情境的官方 S0／S1 WP、輔助 RE 與人工成本下的條件式門檻。下文原定未來策略工作、驗收順序及模型要求保留為歷史規劃與延伸研究，不再是目前主線待辦；詳見[範圍決議](../reports/archive/phase3/phase3_scope_decision_2026-10-01.md)。

## 研究目的與輸出

回答第 1–9 局、每隊初始兩次 Challenge 時，Decision Team 應立即挑戰或保留額度。成功保留、失敗扣一；比較剩餘 1 次與 2 次，0 次是不可挑戰的價值基準。核心只區分進攻方／防守方，pitcher／catcher 分析及延長賽策略列為延伸。

預定輸出原判維持 S0、翻判 S1 的 RE／WP、差值，以及在指定辨識成功機率下的策略與 RRA。WP 為策略目標，RE 作輔助解釋／靜態基準，不任意混成單一加權目標。正式策略尚未完成，不能將合成示範當成實證成果。

2026-10-01 主線執行順序更正：先回答**已可提出挑戰的當下**，挑戰隊伍 `WP(S1)−WP(S0)`、指定主觀翻判率下的立即預期勝率增益，以及可承受的失敗額度成本上限；再以明示的增量額度成本做條件式建議。見[勝率決策主線報告](../reports/archive/phase3/phase3_win_decision_primary_2026-10-01.md)。ABS 停用／replay 來源未知限制完整 Legal 母體的外推，但不阻擋這個條件式決策計算。人工每局未來機會與 WP 損失的合成模型降為次要敏感度檢查，不與官方 WP 疊加當作實證全場價值。

同日最初提供[瀏覽器輸入與 Train-only 兩機會額度成本近似](../reports/archive/phase3/phase3_option_value_and_ui_2026-10-01.md)。其後依[重新設計方案](../reports/archive/phase3/phase3_option_value_redesign_plan_2026-10-01.md)撤下舊模型的主要單一門檻：現行介面先顯示官方 WP／RE 的兩判決差值，WP 表外仍保留 RE，再以預宣告的人工零／低／高失敗額度成本列條件式門檻敏感度與可選自訂成本。這些成本不是已識別的 `V(S,c)`，門檻範圍不是信賴區間或正式 RRA；舊模型結果僅留歷史研究紀錄。

## 固定估值來源

- 主線使用既有 `savant-baseline-v2`，不重新訓練 WP。原始 bundle 為 2026-09-14，修正後 v2 為 2026-09-15；實驗必須記錄實際檔案 SHA-256，不能只記日期。
- WP 保存主隊視角，轉為 Decision Team 視角時遵守 ADR-0001；兩個反事實必須使用同份快照。
- 官方 RE288 用於原半局的立即得分加剩餘 RE；第三出局剩餘 RE 為零。不能拿換邊後的對手 RE 替代。RE 不受 WP 的 ±5 分欄位限制。
- 逐球 `home_win_exp`／`bat_win_exp` 或 observed delta 不能取代兩個反事實狀態的查表。
- 九局結束平手保留 `savant-regulation-tie-home-v1`（主隊 0.5）的來源與版本，未來需做邊界敏感度分析；不是實際終場，也不研究延長賽挑戰。

## 兩層支援性閘門

### 當前反事實估值

S0、S1 的非終局狀態都必須能查表；查表範圍為主隊分差 −5 至 +5，必須檢查轉移後狀態，不能只看投球前分差。已確定勝負的合法終局可依規則給 0／1，九局平手走專用邊界，不應誤報為普通查表缺值。

保留真實分差。超界不截尾、不當成「5 分以上」的合併格、不插補。unsupported compound event、invalid state、來源缺漏與單純表格超界需分開報告。若只有 RE 可估值，可保留 RE 與 WP 缺值原因，不輸出假造的 WP 或 RRA。

Phase 1 的三場 16 次中 12 次可估值、4 次缺值，只是開發樣本，不能外推成整季覆蓋率。

### 未來策略求值

即使當前 S0／S1 都在表內，未來仍可能超界並回到範圍內。正式策略前必須指定跨界分支的 continuation／停止條件、對手策略及敏感度分析，報告受影響分支的機率質量與結果穩健性。

不得靜默刪掉跨界路徑、事後只選從未超界的比賽、將剩餘 Challenge 價值設為零，或默認大比分必勝／必敗。若只能定義有限視野模型，必須明稱有限視野策略，不宣稱全場最適。本項尚待研究與驗收。

## Future Opportunity 不是只預測次數

至少需要機會到達時間、條件狀態／估值分布、挑戰成功機率假設，以及行動造成的後續狀態變化。先做可解釋的經驗／統計基線，不強制使用 XGBoost；模型複雜度由樣本外表現決定。

資料不能只用 actual attempts。Legal Opportunity 依歷史剩餘額度而受限制，零額度時沒有 legal opportunity 不代表沒有潛在不利判決；必須另追蹤候選判決、資格與額度，處理歷史策略造成的選擇偏差。Reasonable label 若使用事後位置，只能作分析標籤，不作部署特徵或不加說明的主母體篩選。

ABS technical outage 與 post-replay-review 排除尚未完成，維持 `provisional_source_limitations`。不能因 Phase 0 通過而改稱完整 Legal population。

## 年份與評估

- Dataset A 原切分（Train 2019／2021–2023、Validation 2024、Test 2025、External 2026）保留供自建模型延伸，不是本次官方 WP 的訓練流程。
- 官方頁面宣告 2016–2025，RE 回應標示 2025，兩者語意不同；2025 不能宣稱是官方 WP 完全獨立的樣本外測試。
- Dataset B 的機會模型需在估計前另行鎖定符合兩次制度、Challenge format 已確認的時間 cohort、game-level split 與排除規則；2023–2025 不得不看 regime 就混合。
- 2026 可作來源年份之後的外部檢查，但已用於開發的比賽（至少 823244、823569、825027，以及其他實際參與調整的樣本）不得重新宣稱未見測試；須維護完整開發清單。
- 固定 WP 的 Brier／Log Loss／校準曲線是外部模型診斷，不是本專案完成訓練校準的證據。報告涵蓋率、分組支持量與以比賽為單位的不確定性。
- Policy 比較使用一致母體與估值假設；不可把已觀測未來球序直接當成挑戰後仍不變的反事實。模擬勝率提升是模型條件下的估計，不是實際因果增勝。

## 執行順序與現況

1. 固定官方 WP 主線契約及 Issue：本次文件交付。
2. 官方表格覆蓋驗證：六場先導樣本已完成；2026-09-24 跨年度工程 cohort 的 24 場 feed、9 日完整逐球及 ABS-only CSV 已取得，18 場兩次制均可建立 provisional opportunity 母體，2,218／2,489 有額度候選兩側皆可查 WP（89.11%）。780464 的 `AB` 非投球事件已嚴格對齊，年度／制度、比賽、決策狀態及逐筆 S0／S1 缺值原因已輸出；coverage 不是完整 Legal population，也不是樣本外政策評估。見 [清冊與來源限制](../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。
3. 完整機會母體與跨界 continuation 設計：Issue 02／03 中 24 場來源訊號已盤點，ABS outage／replay 逐球資格仍全數未知，需維持 provisional estimand；合成有限樹已驗證表外回表、未知區間、額度與九局平手邊界的工程契約，但真實未來分支機率及正式 continuation 仍未鎖定。見[資格與切分報告](../reports/archive/phase2/dataset_b_readiness_2026-09-24.md)及[合成契約報告](../reports/archive/phase2/official_wp_continuation_contract.md)。
4. Future Opportunity 基線與時間驗證：Issue 04；Dataset B 的 96 場賽程候選及時間窗保持固定。2026-09-29 已嚴格復原 6 場缺漏 Challenge，另 5 場無法定位而整場排除；91 場／13,132 筆風險集通過輸入閘門，第一版到達 hazard 已以右設限 likelihood 完成 Train／Validation／Test／名義 External 評估。External 的遊戲層級不確定區間含零，Brier 無一致改善；來源資格、缺漏敏感度及完整開發清冊仍未驗收，正式 Legal Opportunity、holdout 與策略 readiness 仍為 false。見[復原與輸入閘門](../reports/archive/phase2/dataset_b_challenge_recovery_2026-09-29.md)及[基線結果](../reports/archive/phase2/dataset_b_observational_baseline_2026-09-29.md)。

   同日[行動與設限稽核](../reports/archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md)發現原「九局設限」混入至少 45 筆額度耗盡、另 6 筆不明，舊 hazard／NLL／Brier 不得作已校正策略輸入。Train 12 個局數×攻守×額度行動支持格僅 2 格通過最低門檻；需先另版重建行動後資源終止、重新估計並明示不可識別的反事實假設。

   隨後[額度感知重估](../reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md)由官方 feed 解出 6 筆中的 5 失敗／1 成功，確定 50 筆當下額度耗盡、132 筆額度仍在時九局設限。新版只對後者與 12,950 筆已觀察到達者 fit 事後條件 hazard；`post_action_budget` 為行動後才知，不能直接代替挑戰前可用的策略轉移模型。

   同階段後續已盤點固定五場缺漏的假設情境、九局右設限，以及已觀察下一機會的方向與 WP 價值類別分布；見[敏感度與分布報告](../reports/archive/phase2/dataset_b_followup_sensitivity_2026-09-29.md)。這補足觀察性基線的一部分，但沒有估計不同 Challenge 行動後的未來狀態、完整 Game State 分布或正式 continuation。
5. 決策時情境原型：2026-09-30 已用同一介面處理單一狀態及固定 Dataset B cohort，只使用判決前特徵與官方 S0／S1 估值，在**人工**成功率／未來額度價值格點下計算挑戰與保留的相對差。91 場的 13,132 筆暫定候選中，11,060 筆兩側 WP 可估，2,072 筆維持不支援；Test 在 `p=0.50` 時，小／大額度成本下的建議差異明顯。這是敏感度盤點，不是球員成功率預測、因果增勝、正式 Dynamic Policy 或 RRA；見[原型報告](../reports/archive/phase3/policy_scenario_prototype_2026-09-30.md)。
6. 修訂後 Phase 2 限定收尾：2026-10-01 已重驗固定 96／91／5 場處置、13,132 筆第 1–9 局候選及全部未知的來源資格；7 場納入比賽雖進入延長賽，延長局決策未進主要母體。直接九局平手終局的人工邊界壓力測試有 1 筆候選建議可翻轉，不能推論較早局數的未來政策穩健。見[收尾報告](../reports/archive/phase2/official_wp_phase2_closeout_2026-10-01.md)。限定資料與原型證據包已收尾；正式 Legal、反事實轉移、表外實證 continuation、完整開發清單與正式 Policy Gate 仍為 false。
7. Phase 3 第一輪假設式九局模型：2026-10-01 已用人工每局未來機會、相對 WP 損失及未來翻判率倒推 `V(S,0/1/2)`，於固定 91 場比較永不挑戰、固定信心門檻及動態原型；可估值與不支援分開，合成 RRA 隨情境顯著變動。見[第一輪報告](../reports/archive/phase3/phase3_synthetic_regulation_policy_2026-10-01.md)。這不是完整 Game State 轉移、實證表外 continuation 或樣本外政策績效；Issue 05 仍 claimed，正式 Dynamic Policy／RRA readiness=false。

已完成的 Phase 2 Dataset A、RE 開發估計、對齊與離線重播全部保留。全季下載、壓縮儲存、自建 WP 訓練與整合暫緩；不刪資料、不改既有 schema／split。正式 policy readiness 仍為 false。工作拆分見 [工作地圖](../.scratch/official-wp-policy/map.md)。
