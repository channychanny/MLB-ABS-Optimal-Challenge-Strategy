# 官方 WP 主線 Phase 2 限定收尾驗收

日期：2026-10-01。結論：**第 1–9 局、固定官方 WP 的 Phase 2 資料與原型證據包已收尾，可進入「明示假設的 Phase 3 原型」；正式 Phase 2／Policy Gate 未通過。** 這是兩個不同判定，不把未知來源資格、人工邊界或情境成本稱為實證模型。舊自建 WP Phase 2 工作線維持暫緩，並非追認為完成。

## 固定範圍與可重播輸入

- 只研究第 1–9 局、每隊初始兩次挑戰、Decision Team 進攻／防守方。第十局以後只留在完整比賽 feed 與官方終場計數稽核，不進主要候選或策略估計。
- 使用原固定 96 場賽程選樣及既有 Train／Validation／Test／名義 External 時間窗；91 場逐球與官方計數通過，5 場挑戰事件無法定位而整場排除、不替補：`752127`、`753397`、`753580`、`780468`、`780929`。91 場中有 7 場實際進入延長賽（Train 3、Validation 2、External 2），但全部 13,132 筆主要有額度候選的決策局數都在 1–9 局。
- 13,132 筆暫定候選中，11,060 筆兩側官方 WP 可查、2,072 筆不支援。Train／Validation／Test／名義 External 分別為 5,256／1,435／1,579／2,790 筆可估；所有缺值仍保留，不截成 ±5、不補零。
- 13,132 筆的 `abs_technical_availability` 與 `post_replay_challenge_eligibility` 均為 `unknown`。來源沒有足以逐球驗證全場 ABS 停用區間或 replay 順序的完整欄位；「沒找到線索」不等於合法。因此母體只能稱 `provisional_opportunity`，不能稱完整 Legal Opportunity。
- 情境結果重新對 91 場候選檔 SHA、固定官方 WP 估值及四個切分數量核對；`actual_challenge`、`overturned`、`post_action_budget` 與觀察性到達標籤都不是決策時輸入。39 場已知開發清單與候選場無交集，但清單的完整性仍是 `known_project_samples_only`，故不宣稱正式 holdout。

## 九局平手與表外支援

官方基準的九局平手主隊 WP 為 0.5。為測試直接接到此終點的 S0／S1 分支，另以**人工**主隊值 0.25、0.40、0.50、0.60、0.75 重算同一狀態；這些不是經驗可信區間，也不模擬第十局挑戰。以 `large_resource_cost`、人工翻判成功率 0.50 為固定檢查情境，13,132 筆中只有名義 External 的 `game_pk=824191`、打席 75／第 4 球直接碰到九局平手終點：參考值 0.50 建議挑戰，0.60／0.75 改為保留，0.25／0.40 不變。WP 支援狀態在所有格點均未改變。

此檢查**只限當前 S0／S1 直接終局**。較早局數若將邊界變動沿未來球序傳遞，仍需已識別的未來轉移；不能用「只有 1 筆直接受影響」推論整體策略對邊界穩健。現有[合成跨界契約](official_wp_continuation_contract.md)已驗證表外路徑可回表、未知終點須保留區間，但沒有真實未來路徑機率。官方 WP 的 ±5 支援與未來 continuation 是兩個閘門；後者尚未完成。

## Phase 2 驗收表

| 修訂後 Phase 2 項目 | 本次判定 | 不能升格的部分 |
| --- | --- | --- |
| 固定官方 WP／RE288、主客視角及九局平手來源 | 限定完成 | 官方快照不是本專案訓練的 WP；九局平手仍需完整後續敏感度 |
| 固定 cohort、S0／S1 覆蓋與缺值分類 | 限定完成 | 5／96 場排除可能非隨機；2,072 筆仍不支援 |
| 候選機會、額度與來源資格 | 工程母體完成，Legal Gate 未通過 | 13,132 筆 ABS 停用／replay 資格未知 |
| 時間切分及開發場排除 | 已鎖定已知清單 | 完整開發清單與正式 holdout 未驗收；2025 不是官方 WP 完全獨立測試 |
| 表外 continuation、九局平手及決策視野 | 第 1–9 局與合成契約已鎖；直接終局 stress test 完成 | 真實行動依賴轉移、未來表外質量與邊界傳遞未識別 |
| 進入下一階段 | **可做明示假設的策略原型** | `formal_legal_opportunity_ready=false`、`counterfactual_transition_ready=false`、`formal_policy_evaluation_ready=false` |

## 重播與版本

執行規格為 [`phase2_closeout_protocol.json`](../config/phase2_closeout_protocol.json)，程式為 [`phase2_closeout.py`](../src/abs_challenge/phase2_closeout.py)。在保有相同本機忽略追蹤資料時執行：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.phase2_closeout --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --baseline-result data/processed/dataset_b_observational_baseline_2026-09-29-v3.json --cohort-result data/processed/policy_scenario_cohort_2026-09-30-v4.json --output data/processed/phase2_closeout_replay.json
python -m unittest discover -s tests -v
```

本機 `data/processed/phase2_closeout_2026-10-01-v3.json` 與另一路徑 `v4.json` 重播完全相同，SHA-256 均為 `6E4951B40317EC58EBFAC528A01DF6DFC00713F5747005A8965B117155684A14`。輸出保存輸入 manifest、來源檔指紋及執行版本；來源和 JSON 受 `.gitignore` 排除，其他 clone 不會自動具備。工作目錄仍有未提交變更，此結果是開發稽核，不是乾淨 commit 的正式實驗。

## 下一階段邊界

Phase 3 應先做**九局內、明示假設且可回傳「無法判定」**的策略原型：成功率、兩行動後續狀態、額度轉移、對手策略與表外終點各自版本化；用相同候選母體報告支持／不支持及假設翻轉，不將歷史實際球序當反事實。若要宣稱正式 Dynamic Policy／RRA，須另取得足夠資格來源及行動支持，估計或保守界定未來分支，完成邊界傳遞與評估驗收；本報告不授權這項宣稱。
