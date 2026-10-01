# Dataset B 額度感知到達契約與條件基線

日期：2026-09-29。本輪接續[行動支持與設限稽核](dataset_b_action_support_and_censoring_2026-09-29.md)，不覆寫原 91 場候選或第一版到達結果。研究母體仍是固定 96 場清冊中的 91 場可完整核對比賽、13,132 筆第 1–9 局有額度暫定機會；五場來源缺漏比賽保持排除，Test／名義 External 不參與選模。

## 來源重建與新版 episode 契約

新版程式 [`dataset_b_resource_aware.py`](../src/abs_challenge/dataset_b_resource_aware.py) 離線重新驗證逐場官方 feed manifest、原候選 SHA-256、逐球挑戰事件鍵與挑戰隊伍。六場嚴格復原比賽另核對原準備報告保存的 ABS-only 對齊證據。91 場的 367 次實際挑戰皆一對一對應；剩 1 次額度的挑戰有 50 次失敗、52 次成功，剩 2 次則有 124 次失敗、141 次成功。程式逐筆驗證同隊相鄰候選的前後額度一致；不依結果猜測未知挑戰，也不重建反事實球序。

舊稽核以「後續零額度候選」證實至少 45 筆耗盡；另外 6 筆最後挑戰沒有同隊後續候選。這 6 筆現已從既有官方逐球來源直接核對：5 次失敗、1 次成功。因此 182 筆沒有下一同隊有額度候選，確定分為 **50 筆當下額度耗盡**及 **132 筆額度仍在、至九局結束未再到達**。其中 1 筆額度耗盡恰逢全場最後一顆物理投球，新契約另以 `regulation_end_coincident=true` 標示，不把兩個邊界誤認成兩筆獨立樣本。來源資訊與分析時點不同：挑戰是否成功只能在行動發生後知道，不能作挑戰前的預測特徵。

新版每筆 episode 明示 `pre_action_budget`、`actual_challenge`、`challenge_overturned`、`post_action_budget`、`outcome`、`regulation_end_coincident` 與 `gap`。若失敗使額度變 0，`outcome=budget_exhausted` 且 `gap=0`，它是**即時資源終止**，不是延續到九局末的右設限。若額度仍大於 0，下一同隊有額度候選為事件；否則僅在 regulation 結束時右設限。零額度候選可用來驗證轉移，但始終不是合法可挑戰機會。

| 切分 | 暫定機會 | 當下額度耗盡 | 仍有額度且下一機會已觀察 | 仍有額度但九局結束 |
| --- | ---: | ---: | ---: | ---: |
| Train | 6,297 | 26 | 6,211 | 60 |
| Validation | 1,636 | 4 | 1,612 | 20 |
| Test | 1,828 | 6 | 1,804 | 18 |
| 名義 External | 3,371 | 14 | 3,323 | 34 |
| 合計 | 13,132 | 50 | 12,950 | 132 |

## 額度仍在時的觀察性條件到達模型

設定預先寫在 [`dataset_b_resource_aware_protocol.json`](../config/dataset_b_resource_aware_protocol.json)。50 筆即時終止先作獨立終止類型計數，不假裝成等待時間；其餘 13,082 筆才進入「**歷史行動及其成功／失敗已發生後、額度仍在**」的條件到達 hazard。比較整體幾何離散 hazard 與球數×`post_action_budget` 的收縮分層 hazard。只以 Train 擬合，Validation 在整體及 25／100／400 投球曝光先驗中選擇；Test 與名義 External 鎖定評估。這是事後條件預測，不是決策當下的模型，亦不能直接置入 Dynamic Policy。

Train 的條件模型使用 6,271 筆、6,211 次觀察到達、60 次九局右設限，共 23,743 個投球曝光；整體 hazard 為 0.26159／投球曝光。Validation 選出收縮強度 400 的分層模型。主要評估如下，數值愈低愈好：

| 切分 | 整體每曝光 NLL | 分層每曝光 NLL | 分層−整體每 episode NLL 的遊戲 bootstrap 95% 區間 |
| --- | ---: | ---: | --- |
| Validation | 0.57460 | 0.57430 | 僅用於選模 |
| Test（12 場） | 0.58213 | 0.58080 | −0.00848 至 −0.00123 |
| 名義 External（24 場） | 0.56673 | 0.56630 | −0.00465 至 0.00141 |

Test 的條件式 likelihood 有小幅改善；External 區間包含零，不能宣稱跨來源穩定勝出。5 球 Brier 在 Test 為 0.15188→0.15043、External 為 0.16789→0.16703，但 10／20 球視野並非一致改善。上述數值與舊基線**估計母體和條件欄位不同**，不可把兩版 NLL 直接相減當作新契約的預測增益；新版的主要進展是修正資源終止與設限語義。

## 可重播性與尚未過關項目

本機忽略追蹤的逐 episode 契約為 `data/processed/dataset_b_resource_aware_episodes_2026-09-29-v5.json`，評估為 `data/processed/dataset_b_resource_aware_arrival_2026-09-29-v5.json`。v1／v2 的 episode 內容完全一致；v3 起加上同時碰到兩種終點的稽核旗標；v4／v5 加嚴母體與額度不變式後，主要到達評估值不變。具備相同本機快取時，可用新輸出路徑離線重播：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.dataset_b_resource_aware --baseline data/processed/dataset_b_observational_baseline_2026-09-29-v3.json --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --episodes-output data/processed/dataset_b_resource_aware_episodes_replay.json --output data/processed/dataset_b_resource_aware_arrival_replay.json
```

`post_action_budget` 及挑戰結果**只能在實際行動後取得**；本模型估計的是歷史路徑的條件分布，不能由「挑戰／保留」兩組差異識別另一行動的結果。Train 12 個粗粒度行動支持格仍只有 2 格達最低門檻。ABS 停用／replay 資格未知、五場 Train 排除可能有選樣偏差、完整開發清冊未驗收、官方 WP 表外 continuation 未定，故 `decision_time_counterfactual_ready=false`、`formal_legal_opportunity_ready=false`、`formal_dynamic_policy_ready=false`。下一步若研究策略，需明示挑戰成功率來源與私有訊號限制，將失敗扣額度／成功保留作結構化分支，並針對未識別的後續球序做情境與敏感度界限；不可把本模型直接當因果轉移。

本輪工作目錄仍有未提交變更，不能稱正式乾淨 commit 的註冊實驗；沒有推送資料或結果。
