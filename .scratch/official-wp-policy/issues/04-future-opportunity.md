# 04 — Future Opportunity 基線

Type: task  
Status: deferred

2026-10-01 主線範圍收斂：停止把下一次不利判決到達率推成未來「值得挑戰」機率或額度期望值，不續訓正式未來機會模型。已完成觀察性模型與稽核保留歷史證據，不作即時決策成本。見[範圍決議](../../../reports/archive/phase3/phase3_scope_decision_2026-10-01.md)。下文狀態為當時紀錄。

依賴 Issue 01／02／03 的契約。先建立可解釋的經驗或統計模型，輸出到達時間及條件狀態／價值分布，不只預測剩餘次數；納入行動依賴轉移與明示成功機率假設。

驗收前鎖定 Dataset B 時間切分，以 game_pk 分組，排除已用於開發的 external 場次；未知 regime 不混入兩次核心 fit。只能使用決策時已知特徵，記錄樣本支持、稀疏狀態 fallback、機率校準與樣本外比較。不能以事後球序充當改判後的真實路徑。XGBoost 不是必要條件。

2026-09-24：已預宣告兩次制的 Train／Validation／Test／External 時間窗，建立 39 場已知開發排除清冊與重複場次／交疊窗防護；但新場次抽樣方法、game_pk 清冊、樣本量及來源 manifest 尚未鎖定，且來源資格仍 provisional。見[切分計畫](../../../config/dataset_b_split_plan.json)與[預備報告](../../../reports/archive/phase2/dataset_b_readiness_2026-09-24.md)。本 Issue 維持 open，不啟動訓練。

2026-09-24 後續：已依固定 seed、時間窗及配額，從五份官方賽程 metadata 鎖定 96 個候選 `game_pk`；與 39 場已知開發樣本交集為 0，離線重播指紋一致。詳見[賽程候選清冊報告](../../../reports/archive/phase2/dataset_b_schedule_lock_2026-09-24.md)。這僅是賽程候選，仍需逐場確認制度及來源資格；正式 holdout 與模型訓練維持未完成。

## Comments

2026-09-29 額度感知續作：以已快取官方 feed 與既有 ABS-only 復原證據重新核對 91 場／367 次挑戰，前次候選序列無法判定的 6 筆為 5 次失敗、1 次成功。新版契約將 13,132 筆分成 50 筆即時額度耗盡、12,950 筆下一同隊機會已觀察、132 筆額度仍在的 regulation 設限；後兩類用 Train 擬合事後條件 hazard、Validation 選 alpha 400、Test／名義 External 評估。詳見[額度感知報告](../../../reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md)。這只解決資源終止的資料契約與歷史路徑模型，`post_action_budget` 不可作決策前特徵，反事實 Future Opportunity、Legal 資格及正式策略仍未完成；Issue 保持 claimed。

2026-09-29 行動支持與設限複核：91 場／13,132 筆候選中，原 182 筆「regulation_end」至少 45 筆有後續同隊零額度候選，另 6 筆剩 1 次實際挑戰後額度結局不明；原 hazard／NLL／Brier 不得作已校正的到達模型。Train 歷史挑戰僅 155／6,297 筆，12 個局數階段×攻守×額度格只有 2 格達最低雙臂支持。此 Issue 保持 claimed 而非 resolved；先另版重建行動後額度與耗盡終止，重新 Train／Validation／Test／名義 External 評估，且不得將觀察性行動差異視作因果效果。見[稽核報告](../../../reports/archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md)。

2026-09-24：96 場 feed 均已取得，85 場通過逐球對齊並形成 13,252 個暫定判決候選；11 場官方終場 Challenge 計數不符仍保留失敗，未依結果補場。已另存同隊下一候選的觀察性到達間隔與右設限標籤，仍未解決行動依賴轉移、選擇偏差及 ABS 停用／replay 來源資格；`training_ready=false`。詳見[訓練前準備報告](../../../reports/archive/phase2/dataset_b_pretraining_preparation_2026-09-24.md)。

2026-09-29：11 場不符中 6 場用 ABS-only、整場逐球與官方分隊計數唯一定位；5 場無法定位而整場排除，不替補。新版到達標籤僅以同隊下一個有額度暫定候選為事件，91 場／13,132 筆風險集通過[限定觀察性輸入閘門](../../../reports/archive/phase2/dataset_b_challenge_recovery_2026-09-29.md)。本 Issue 仍為 claimed：尚未訓練、校準或評估；完整 Legal population、行動依賴反事實轉移及正式 holdout 仍未就緒。

2026-09-29 基線第一輪：完成 pooled constant hazard 與球數×剩餘額度 24 格收縮 hazard 比較；只用 Train 擬合，在 Validation 選擇 25 pitch-exposure 收縮強度，Test／名義 External 鎖定評估。Test 負對數似然由 0.56000 降至 0.55694，遊戲 bootstrap 差異每 episode −0.0124（95% CI −0.0269 至 −0.0008，12 場）；External 由 0.54553 降至 0.54335，差異 −0.0094（95% CI −0.0325 至 0.0096，24 場）。Brier 無一致改善，External CI 含零。詳見[結果與限制](../../../reports/archive/phase2/dataset_b_observational_baseline_2026-09-29.md)。Issue 繼續 claimed：缺漏／設限敏感度、價值分布、歷史行動依賴與成功率假設尚未完成。

2026-09-29 同階段延伸：固定五場缺漏的假設性 Train 情境使整體 5 球到達機率在 0.7403–0.7557 之間（原 0.7499）；非識別界限。Train 的右設限 64／86 由九局起始；錯刪設限會把 hazard 由 0.2421 推至 0.2644。已觀察下一機會的方向分層模型在 Test／名義 External log loss 改善；價值類別模型在 External 的遊戲 bootstrap 區間含零，unsupported 獨立保留。見[延伸報告](../../../reports/archive/phase2/dataset_b_followup_sensitivity_2026-09-29.md)。Issue 繼續 claimed：完整下一 Game State 分布、行動依賴轉移、成功率假設與正式資格仍待處理。

2026-10-01 主線決策支援：以[Train-only 兩個未來同隊不利判決近似](../../../reports/archive/phase3/phase3_option_value_and_ui_2026-10-01.md)提供失敗額度的模型條件式參考成本；零額度後續判決也保留，Validation／Test／名義 External 只做診斷與套用，未來 WP 缺值另列。它估的是歷史球序上局數×攻守的機會率與可估價值，**不是**改選挑戰後的反事實 Game State 或正式 `V(S,c)`；Issue 保持 `claimed`。

2026-10-01 後續更正：舊兩機會模型已撤離即時介面的主要成本／門檻，保留程式與結果供診斷。依[Issue 07](07-option-value-redesign.md)先審計不同價值的未來機會、下一 Game State 支持與可辨識範圍，不直接把歷史實際球序當成行動反事實；本 Issue 仍 `claimed`。
