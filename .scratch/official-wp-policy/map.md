# 官方 WP 與 ABS 策略主線工作地圖

Type: effort  
Status: open

2026-09-24 已完成六場先導及 24 場跨年度工程 cohort 的 provisional opportunity 覆蓋初檢；主要兩次制 18 場事件序列均可對齊，分組支援已輸出。代表性抽樣、完整資格與未來分支驗證尚未完成。契約見 [spec](spec.md) 與 [官方 WP 主線](../../docs/official_wp_policy.md)。

**2026-10-01 最新主線：**依[範圍決議](../../reports/archive/phase3/phase3_scope_decision_2026-10-01.md)，不再預測未來「值得挑戰」機會或額度期望值。Issue 03／04／05／07 的未來模型部分改為 `deferred`，並非已完成；現行條件式決策品質由 [Issue 08](issues/08-current-decision-quality.md) 追蹤。以下逐項歷史里程碑仍保留。

## 執行順序

- [01 — 官方 WP 覆蓋率驗證](issues/01-coverage.md)：claimed；2026-09-22 六場 1,876 球通過，暫定機會 706／962 可估值；80 個零額度候選另留，actual attempts 修正為 22／29。2026-09-24 固定跨年度 cohort 的 18 場兩次制均完成事件對齊，2,218／2,489 個有額度暫定機會兩側可估值；年度／制度、比賽、決策狀態及逐筆 S0／S1 缺值原因已輸出，來源資格與代表性仍未驗收。見 [清冊與來源限制](../../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。
- [02 — 機會母體與來源限制](issues/02-opportunity-population.md)：claimed；24 場 feed 的來源線索及 2,751 個候選的技術／replay 未知資格已明示，仍無可驗證的完整排除區間；legal population 繼續 provisional。見[資格與切分預備報告](../../reports/archive/phase2/dataset_b_readiness_2026-09-24.md)。
- [03 — 未來分支與邊界設計](issues/03-continuation.md)：deferred；已完成合成有限樹契約測試，但正式未來 continuation 不再屬主線。見[合成報告](../../reports/archive/phase2/official_wp_continuation_contract.md)。
- [04 — Future Opportunity 基線](issues/04-future-opportunity.md)：deferred；歷史不利判決到達率與後續分布保留作資料研究，**不能代表未來值得挑戰的機會或額度價值**。舊 hazard 曾有設限錯誤，已另版重估；正式反事實仍未識別。見[行動與設限稽核](../../reports/archive/phase2/dataset_b_action_support_and_censoring_2026-09-29.md)與[額度感知重估](../../reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md)。
- [05 — Dynamic Policy 與 RRA 評估](issues/05-policy-evaluation.md)：deferred；正式 `V(S,c)`、最優政策與 RRA 不再作主線。既有單步情境與合成九局模型保留歷史證據，不冒稱實證增勝；眼前條件式決策由 Issue 08 接續。
- 2026-10-01 使用介面與未來額度近似：[本機瀏覽器表單及 Train-only 兩機會成本模型](../../reports/archive/phase3/phase3_option_value_and_ui_2026-10-01.md)保留歷史紀錄；現行介面以官方 WP／RE 為主，兩機會模型已撤離即時門檻，只列預宣告的成本假設敏感度，非正式策略。
- [06 — Phase 2 限定收尾](issues/06-phase2-closeout.md)：resolved；2026-10-01 完成固定第 1–9 局候選、來源未知及直接九局平手邊界的重播稽核，**只授權明示假設的 Phase 3 原型**，不代表完整 Legal／正式 Policy Gate 通過。見[收尾報告](../../reports/archive/phase2/official_wp_phase2_closeout_2026-10-01.md)。
- [07 — 額度價值模型重新設計與可行性審計](issues/07-option-value-redesign.md)：deferred；[第一輪固定母體稽核](../../reports/archive/phase3/phase3_decision_time_feasibility_2026-10-01.md)已完成，後續未來機會／額度價值建模因研究範圍收斂而停止，不標作驗收完成。
- [08 — 眼前挑戰情境的條件式決策品質](issues/08-current-decision-quality.md)：open；核對官方 WP／RE 估值、成本情境、缺值、介面說明及研究限制，不估未來好挑戰機會。

2026-09-29 Issue 04 後續已完成[額度感知新版契約與條件到達重估](../../reports/archive/phase2/dataset_b_resource_aware_arrival_2026-09-29.md)：官方來源補明 6 筆候選序列無法判定者的結果，最終 50 筆額度耗盡、132 筆 regulation 設限。這修正了舊模型的資源終止語義，但新 hazard 使用行動後額度，只能描述歷史存活者路徑。當時 Challenge 成功率假設、未觀察私有訊號、反事實後續狀態、Legal population 與表外 continuation 未過關；2026-10-01 後續範圍決議已將正式未來建模改列延伸。

## 保留與暫緩

[原 Phase 2 工作地圖](../phase2-models/map.md) 的已完成項目維持 resolved；未完成的全季取得、壓縮、自建 WP 與整合暫緩。暫緩不代表完成，也不取消既有資料防洩漏與重播契約。
