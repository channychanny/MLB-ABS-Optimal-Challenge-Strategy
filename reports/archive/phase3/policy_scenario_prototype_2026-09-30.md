# ABS 挑戰時機：決策時情境原型與敏感度盤點

日期：2026-09-30。這是固定官方 WP／RE288 主線上的**單一決策時情境原型**，回答「在明示成功率與未來額度價值假設下，現在挑戰還是保留？」；**不是**已識別的 Dynamic Policy、正式 RRA、真實增勝或球員信心預測。主要範圍只含第 1–9 局、初始兩次制及 Decision Team 的進攻／防守方向。延長賽挑戰策略不在本輪。

## 模組介面與輸入隔離

純計算模組為 [`policy_scenarios.py`](../src/abs_challenge/policy_scenarios.py)：單一狀態呼叫 `evaluate_state(baseline, state, original_call, budget, protocol)`，既有候選則使用同一個 `evaluate_valuation(valuation, budget, protocol)`。兩者只依判決前 Game State、原判、決策方、剩餘額度，以及固定官方快照計算的 S0／S1 WP／RE。批次載入時，重新核對 91 場候選 SHA、來源官方快照 SHA、固定四個切分的場次／候選筆數；非複合候選另逐筆重算官方 S0／S1 WP／RE，若與舊檔不一致便停止。`actual_challenge`、`overturned`、`post_action_budget`、到達標籤與事後投球路徑完全不進建議介面。

單一狀態查詢須明示 `assume_pure_called_pitch=true`；它無法只憑手填狀態核對同球是否另有跑壘事件。固定 cohort 的複合事件仍保留 `unsupported`，不硬估。S0／S1 任一官方 WP 缺值時不計策略、不截尾 ±5 分；RE 若存在仍獨立保留。真正終局分支不再附加不存在的未來額度成本；九局平手採原版本化 regulation boundary，不生成延長賽策略。

## 比較公式及假設

令 ΔWP 為決策方視角的官方 `WP(S1) − WP(S0)`；`p` 為**人工指定**的主觀翻判成功率格點，`K_c` 為失敗而少一單位額度的**人工增量成本**，`γ` 為成功分支相對保留分支的**人工未來位移**。本原型只計相對差：

\[
D(p)=p(\Delta WP+\gamma)-(1-p)K_c.
\]

`D(p)>0` 顯示該情境選「挑戰」，`D(p)<0` 選「保留」，相等顯示 `tie`。若成功淨利益大於零，情境損益兩平機率為 `K_c / (ΔWP + γ + K_c)`；若沒有正向成功利益，輸出「無嚴格挑戰門檻」或「完全無差異」。這是**假設下的損益兩平 p**，不是產品規格所要求、需由完整 `V(S,c)` 推出的正式 RRA。S0 已終局時 `K_c=0`；S1 已終局時 `γ=0`。輸出保留 S0／S1 官方 WP，但不把 `D` 冒稱真實最終勝率。

預先宣告的格點與五組人工檢查情境見 [`policy_scenario_protocol.json`](../config/policy_scenario_protocol.json)：`p=0.25／0.50／0.75／0.90`；失敗成本以決策方 WP 機率為單位，剩 1 次／2 次分別設為：

| 情境 | 剩 1 次成本 | 剩 2 次成本 | 成功後續位移 |
| --- | ---: | ---: | ---: |
| 僅立即判決 | 0 | 0 | 0 |
| 小額度成本 | 0.005 | 0.0025 | 0 |
| 大額度成本 | 0.020 | 0.010 | 0 |
| 成功後續不利 | 0.010 | 0.005 | −0.005 |
| 成功後續有利 | 0.010 | 0.005 | +0.005 |

這些數字是為觀察決策翻轉而設的**人為檢查點**，不是資料估計值、可信上下界或建議球員採用的信心；先前額度感知到達模型使用行動後資訊，本輪刻意不把它當決策前轉移模型。

## 固定 91 場盤點

在 Train／Validation／Test／名義 External 不調整情境格點，僅記錄哪些候選可估值、每格建議如何變化。這不是政策的樣本外績效測試，因為成功率、成本及反事實球序都沒有被識別。

| 切分 | 場次 | 暫定機會 | 雙側 WP 可估 | 不支援 | 所有列出情境都建議挑戰 | 隨情境改變／含 tie |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 43 | 6,297 | 5,256 | 1,041 | 358 | 4,898 |
| Validation | 12 | 1,636 | 1,435 | 201 | 117 | 1,318 |
| Test | 12 | 1,828 | 1,579 | 249 | 125 | 1,454 |
| 名義 External | 24 | 3,371 | 2,790 | 581 | 178 | 2,612 |
| 合計 | 91 | 13,132 | 11,060 | 2,072 | 778 | 10,282 |

「所有列出情境都建議挑戰」只指**本表五組成本與四個 p 格點**，不是對一切合理假設的穩健性保證。沒有一筆在全部格點都嚴格建議保留，因為「僅立即判決、p>0」情境本來就給正向翻判價值；因此 10,282 筆變動是最重要的警示。未支援者包含表外／來源查表缺值及非純判決，沒有以零價值填補。

若只固定 `p=0.50`，成本假設的改變如下；分母只含雙側可估候選：

| 切分 | 小成本：挑戰／可估 | 大成本：挑戰／可估 | 大成本：保留／可估 |
| --- | ---: | ---: | ---: |
| Test | 1,382／1,579 | 643／1,579 | 886／1,579 |
| 名義 External | 2,384／2,790 | 998／2,790 | 1,693／2,790 |

Test 的大成本情境中，損益兩平 `p` 的已定義候選中位數為：剩 1 次 0.690、剩 2 次 0.500；名義 External 分別為 0.667、0.526。這些是人工成本代入的代數結果，**不能**解讀成經驗上球員至少需有這些準確率，更不能稱正式 RRA。結果 JSON 同時保留進攻／防守方、額度及局數階段（1–3／4–6／7–9）的每格計數，避免整體比例掩蓋時機差異。

## 單一狀態範例與使用方式

版本化範例輸入 [`policy_scenario_example_state.json`](../config/policy_scenario_example_state.json) 是五局下、1 出局、一壘有人、2–1 球數、0–0、原判好球、剩 1 次。固定官方快照給決策方 `WP(S0)=0.563`、`WP(S1)=0.588`，立即差 0.025（2.5 個百分點），RE 差約 +0.223 分。若假設 `p=0.25`，小成本情境建議挑戰，大成本情境建議保留；整體回傳 `scenario_sensitive`，而不是一個無條件「最佳」答案。可重播：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.policy_scenarios --state-input config/policy_scenario_example_state.json --output data/processed/policy_scenario_example_replay.json
python -m abs_challenge.policy_scenarios --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --baseline-result data/processed/dataset_b_observational_baseline_2026-09-29-v3.json --output data/processed/policy_scenario_cohort_replay.json
```

本機忽略追蹤的完整結果分別為 `data/processed/policy_scenario_example_2026-09-30-v2.json` 與 `data/processed/policy_scenario_cohort_2026-09-30-v3.json`。另以完全相同輸入重播為 `v4.json`，兩份 cohort 結果的 SHA-256 均為 `75DCE14B1A5A2A7A06D31B3B0966D305F202D4EB9F8B60FB5499198666A62B3B`。結果記錄原檔、官方快照、情境規格及執行版本指紋；`.gitignore` 排除本機資料與結果，其他 clone 不會自動取得。工作目錄仍有未提交變更，不是乾淨 commit 的正式實驗。完整標準函式庫測試 281 項通過。

## 尚未跨過的閘門

- 真實 `p` 需有可驗證的球員資訊或預先指定的情境研究設計；不能把 367 次歷史挑戰的成功率套用至所有 13,132 筆候選。
- `K_c` 與 `γ` 目前未由決策前可用、且經時間外驗證的反事實機會／轉移模型估得。官方 WP 可能已有歷史策略效果，未證明人工增量與它可相加而不重複計值。
- ABS technical outage、post-replay 資格、五場 Train 缺漏、完整開發清冊與表外 continuation 仍未驗收；`formal_legal_opportunity_ready=false`、`formal_policy_evaluation_ready=false`。
- 後續若要升為正式 Dynamic Policy／RRA，需將成功保留、失敗扣額度及雙分支後續狀態放進同一個經來源支持的 `V(S,c)`，並在固定母體上作策略比較與不確定性分析；不能把本輪情境建議對照歷史實際行動就宣稱因果增勝。
