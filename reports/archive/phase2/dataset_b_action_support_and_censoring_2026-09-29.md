# Dataset B 歷史行動支持與額度耗盡設限稽核

日期：2026-09-29。這是固定 96 場候選、91 場納入的 Dataset B **診斷**，不是策略效果估計。使用與既有到達基線相同的 13,132 筆有額度暫定機會、同隊下一候選定義與 Train／Validation／Test／名義 External 切分。輸入準備報告、既有基線及 91 場候選檔的 SHA-256 均重新核對；不修改舊資料或舊結果。

> **後續進展：**本報告當時僅憑候選序列將 6 筆列為無法判定；同日[額度感知新版契約](dataset_b_resource_aware_arrival_2026-09-29.md)從已快取官方 feed 核對出 5 次失敗、1 次成功，最後確定 50 筆額度耗盡、132 筆額度仍在的九局設限。以下 45／6 數字保留為先前證據層級，不代表最新未解數。

## 主要發現：既有「九局設限」標籤混入額度耗盡

舊候選檔將所有沒有下一個同隊有額度候選的 episode 標為 `regulation_end`。本輪檢查同隊後續的**零額度候選**，發現至少 45 筆在該次有額度候選後仍出現零額度候選，因此「直到 regulation 結束前都仍在等待合法機會」不成立。這 45 筆皆為剩餘 1 次時實際發起挑戰，對應挑戰後額度耗盡的直接序列證據。另有 6 筆剩 1 次且實際挑戰、但沒有後續同隊候選，僅由候選檔無法區分額度耗盡與九局終止，保留 `budget_or_regulation_unresolved`，不擅自歸類。

| 切分 | 舊標籤「無下一機會」 | 後續零額度證據 | 剩 1 次挑戰後無法判定 | 其餘無額度耗盡證據 |
| --- | ---: | ---: | ---: | ---: |
| Train | 86 | 23 | 3 | 60 |
| Validation | 24 | 3 | 1 | 20 |
| Test | 24 | 6 | 1 | 17 |
| 名義 External | 48 | 13 | 1 | 34 |
| 合計 | 182 | 45 | 6 | 131 |

既有到達基線在這些 episode 上把額度耗盡後至九局結束的投球也算成「仍可等候下一次有額度機會」的存活曝光，因此先前的 hazard、NLL、Brier 與設限敏感度數值**僅保留為舊分析歷史紀錄，不可作已校正的 Future Opportunity 模型或策略輸入**。本輪不以臆測的失敗時刻改寫原始候選檔；要重估時，必須明確建立「保留額度／挑戰成功保留額度／挑戰失敗扣額度」的行動後資源狀態與額度耗盡終止事件，不能把該事件當成獨立九局設限。既有「已觀察到下一候選」的條件分布仍可作歷史描述，但不能代表任一替代行動的後續分布。

## 歷史挑戰／保留行動的資料支持

檢查規格見 [`config/dataset_b_action_support_protocol.json`](../config/dataset_b_action_support_protocol.json)，程式見 [`src/abs_challenge/dataset_b_action_support.py`](../src/abs_challenge/dataset_b_action_support.py)。先用 Train 固定的 3 個局數階段（1–3、4–6、7–9）× Decision Side（進攻／防守）× 剩餘額度（1／2）組成 12 格。每格需至少 20 次挑戰、20 次保留，兩臂各至少 5 場，挑戰比例在 1%–99%，才算通過**粗粒度支持檢查**。這些門檻是最低樣本診斷，不足以保證因果可識別或完整狀態支持；未依 Test／External 數值調整。

| 切分 | 暫定機會 | 歷史挑戰 | 歷史保留 | 挑戰後觀察到下一同隊機會 | 保留後觀察到下一同隊機會 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 6,297 | 155 | 6,142 | 128／155 | 6,083／6,142 |
| Validation | 1,636 | 43 | 1,593 | 37／43 | 1,575／1,593 |
| Test | 1,828 | 57 | 1,771 | 50／57 | 1,754／1,771 |
| 名義 External | 3,371 | 112 | 3,259 | 96／112 | 3,227／3,259 |

Train 的 12 格中只有 **2 格**通過最低門檻：1–3 局防守方／額度 2（22 次挑戰）及 4–6 局進攻方／額度 2（21 次挑戰）。其餘 10 格未通過，尤其 1–3 局額度 1 的進攻方只有 2 次挑戰、防守方只有 3 次。更細的球數、壘包、出局、分差或 WP 分層只會令這些組合更加稀疏。即便在通過的兩格，玩家對誤判的私有訊號未被觀察，挑戰與保留組也不是隨機分配；上述 128／155 與 6,083／6,142 **不能相減作為挑戰的效果**。挑戰失敗耗盡額度本身亦會機械地降低後續「有額度機會」的可觀察率。

## 結論與下一個可執行里程碑

本輪 `historical_action_overlap_gate_pass=false`、`arrival_baseline_censoring_contract_valid=false`、`counterfactual_transition_ready=false`，因此 `formal_dynamic_policy_ready=false`。原來的 91 場候選與固定切分繼續保留，沒有補造五場缺漏、沒有改用 Test／External 調門檻，也沒有把零額度候選加入可挑戰母體。

下一輪應在新版本資料契約中重建每次挑戰後的額度轉移及額度耗盡終止，將「物理上下一個被動候選球」與「有額度可挑戰的下一機會」分開；用 Train 重新估計並由 Validation 選模，再重新檢查 Test／名義 External。若來源仍不足以處理 outage／replay 與玩家私有資訊，策略只能明示假設做情境／敏感度分析，不能宣稱從歷史資料識別出最優因果策略。五場 Train 缺漏、名義 External 清冊與官方 WP 表外 continuation 仍是獨立未過閘門。

本機結果為忽略追蹤的 `data/processed/dataset_b_action_support_2026-09-29-v4.json`，保留逐切分摘要、12 格支持、來源指紋與執行版本。同一來源重播的結果一致；具備相同本機候選檔時可用新路徑重播：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.dataset_b_action_support --baseline data/processed/dataset_b_observational_baseline_2026-09-29-v3.json --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --output data/processed/dataset_b_action_support_replay.json
```

本輪 Git 工作目錄仍有未提交變更，並非正式乾淨版本實驗；資料與結果未推送至遠端。
