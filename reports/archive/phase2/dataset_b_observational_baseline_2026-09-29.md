# Dataset B 第一版觀察性到達基線

日期：2026-09-29。這是固定 Dataset B 樣本的第一輪估計與時間評估，用來描述歷史實際路徑中，同一球隊距離下一個有額度暫定機會還有幾個物理投球。它不估計 Challenge 的成功率、翻判價值或採取不同決策後會發生的狀態。

> **後續稽核更正（2026-09-29）：**182 筆原標為九局右設限的 episode 中，至少 45 筆有後續同隊零額度候選，證明額度已耗盡；另 6 筆剩 1 次挑戰後無後續候選，額度狀態未能判定。下列 hazard／NLL／Brier 是未區分額度耗盡與九局終止的歷史結果，**不得視為已校正的到達模型或策略輸入**。見[行動與設限稽核](dataset_b_action_support_and_censoring_2026-09-29.md)。

## 事前鎖定的估計方式

設定見 [`config/dataset_b_baseline_protocol.json`](../config/dataset_b_baseline_protocol.json)，程式見 [`src/abs_challenge/dataset_b_baseline.py`](../src/abs_challenge/dataset_b_baseline.py)。每一筆 episode 從一個有額度 `provisional_opportunity` 開始；事件是同隊下一個有額度暫定候選，右設限則是九局結束前未再出現。以物理投球間隔作離散時間，對事件 episode 使用「事件前存活至第 g 球、並在第 g 球到達」的幾何 hazard likelihood；右設限 episode 貢獻截至已觀察間隔的存活 likelihood，不將它當成永不到達。

比較兩個可解釋的模型：

1. **整體基線**：Train 的事件數除以總風險投球曝光數，得到固定的每球 hazard。
2. **狀態分層基線**：依決策時球數（balls、strikes）和剩餘額度分成 24 格；每格 hazard 以固定曝光先驗收縮至 Train 整體 hazard。Validation 從整體模型與 25、100、400 個投球曝光三個收縮強度中選擇。只使用決策時可得欄位，不用 `actual_challenge`、翻判結果、到達標籤或 WP／RE 值作預測特徵。

只用 Train 估計 hazard；Validation 只選模型。Test 與名義 External cohort 不參與選擇，報告鎖定模型對整體基線的比較。主要指標是含右設限事件時間 likelihood 的每個投球曝光負對數似然（越低越好）；另報每個 episode 負對數似然，以及 5、10、20 球視野的 Brier 分數。Brier 只使用截至該視野結果可觀察的 episode，另列可觀察比例。Test／External 的負對數似然差異以 `game_pk` 為單位做 2,000 次固定 seed bootstrap。

## 樣本與估計結果

Train 的整體 hazard 為 0.2421／投球曝光；即在這個簡化幾何模型下，整體事件間隔平均約 4.13 個投球曝光。Train 有 6,297 個 episode、6,211 次觀察到達、86 次右設限，總計 25,658 投球曝光。Train 的 43 場中有 5 場因官方計數缺漏無法定位而排除；原本 Train 候選 48 場，流失 10.4%，可能造成選樣偏差。

| Split | 場次 | Episodes | 觀察到達 | 右設限 | 投球曝光 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 43 | 6,297 | 6,211 | 86 | 25,658 |
| Validation | 12 | 1,636 | 1,612 | 24 | 6,666 |
| Test | 12 | 1,828 | 1,804 | 24 | 7,280 |
| External | 24 | 3,371 | 3,323 | 48 | 14,133 |

Validation 選出狀態分層模型、收縮強度 25。每投球曝光負對數似然如下：

| 評估集 | 整體基線 | 狀態分層模型 | 差異（分層−整體） |
| --- | ---: | ---: | ---: |
| Validation | 0.55317 | 0.55075 | −0.00242 |
| Test | 0.56000 | 0.55694 | −0.00305 |
| External | 0.54553 | 0.54335 | −0.00217 |

遊戲層級 bootstrap 的每 episode 負對數似然差異，在 Test 為 −0.0124（95% 區間 −0.0269 至 −0.0008，12 場），在 External 為 −0.0094（95% 區間 −0.0325 至 0.0096，24 場）。External 區間包含零；這批資料不能證明狀態分層有穩定改善。Test 的 Brier 在 5 球視野略好（0.1550 對 0.1563），10 球及 20 球則略差（0.05345 對 0.05271；0.00939 對 0.00933）。External 三個視野中，狀態模型於 5、10 球略差，20 球略好；沒有一致的 Brier 改善。各視野可觀察比例約 98.9%–99.2%。

因此本輪支持的結論是：固定簡單模型能重現一個條件式到達率基線，狀態分層對 likelihood 有小幅樣本內外改善訊號，但提升有限、Brier 不一致，而且 External 不確定性大。這不是策略可用的因果效果，也不能從目前分數宣稱模型已充分校準或可部署。

## 可重播結果與界限

本機 JSON 結果為 `data/processed/dataset_b_observational_baseline_2026-09-29-v3.json`，包含每個輸入檔及 91 個候選檔的 manifest、所選參數、分割評估、bootstrap、執行環境及 Git 工作目錄狀態。資料檔受 `.gitignore` 排除；重跑前需先有相同的 9/29 候選資料、準備報告與輸入閘門：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.dataset_b_baseline --gate data/processed/dataset_b_limited_model_input_gate_2026-09-29-v4.json --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --output data/processed/dataset_b_observational_baseline_replay.json
```

程序在載入候選前會重新驗證閘門指向的固定選場、政策、準備報告及逐場候選 SHA；若閘門、準備資料、政策或候選檔內容有變就停止。協定為標準函式庫實作，不增加外部 Python 套件。

- 右設限似然假設在本輪稀疏預測條件下非資訊性；九局邊界是否與候選率相關尚未建模。Brier 的早期設限 episode 會排除，因此同時列出 coverage。
- 5 場無法定位的比賽全在 Train，來源缺漏可能不是隨機發生；未完成缺失機制敏感度分析。
- 歷史策略會改變後續額度及狀態；目前預測的是實際路徑，不是採取不同 Challenge 行動後的反事實。
- 來源的 outage／replay 資格仍未知；這是 `provisional_opportunity` 的限定結果，非完整 Legal Opportunity。
- 名義 External 集只有 24 場，且專案開發清冊完整性仍未驗收；不能宣稱為完全獨立的外部驗證。工作目錄在此次執行時未乾淨，故屬可重播的開發分析，不是正式註冊實驗。

下一個研究步驟應先作遊戲階段／設限敏感度，以及五場缺漏的納入流失界限，再決定這個極簡狀態模型是否值得擴充。正式 Dynamic Policy 仍需要明示歷史挑戰對未來轉移的處理及挑戰成功率假設。
