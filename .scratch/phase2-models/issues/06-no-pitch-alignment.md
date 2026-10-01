# 06 — 非投球判決與跨來源逐球對齊

Type: task  
Status: resolved

## 發現與影響

2026-09-16 固定跨年度 20 場樣本中，有 5 場因 Statcast 比 `isPitch=true` 的 feed 多列而被排除。這是正式擴大資料前需解決的高優先問題，不能以目前 15 場通過推定整季無偏。

| 場次 | 日期 | 固定來源觀察 |
|---|---|---|
| 565047 | 2019-05-15 | 打席 78，Statcast 有 4 列 automatic_ball；feed 是 4 個 no_pitch，pitchNumber 均 0，終局為敬遠保送 |
| 564888 | 2019-08-15 | 打席 20，兩個實際投球後另有 2 列 automatic_ball；feed 的 no_pitch 沿用 pitchNumber 2 |
| 718158 | 2023-05-15 | 打席 17 首先自動好球，後續實際投球 Statcast 比 feed 編號多 1；打席 50 另有終局自動第三好球 |
| 718159 | 2023-05-15 | 打席 61 首先自動壞球，之後實際投球 Statcast 比 feed 編號多 1 |
| 745015 | 2024-05-15 | 打席 42 首先自動壞球，Statcast 第 3 球對應 feed 實際第 2 球 |

來源均已保存於 `data/raw/phase2_cache_2026-09-16/`，原始部分結果及排除原因保留於 `phase2_batch_2026-09-16_report.json`。2026-09-16 僅辨識與記錄；2026-09-18 的修正與驗證如下，未覆寫舊來源或舊結果。

## 驗收條件

- 先保存可攜式來源摘錄／合成回歸案例，涵蓋整打席敬遠、投球中途敬遠、起始／中途／終局計時器違規。
- 明確區分實際投球與非投球球數變化；自動判決不得當作 ABS 可挑戰投球。
- 以打席事件順序、球數變化與原始來源欄位交叉驗證，保留兩套原始 pitch number 及對齊證據；不得只依固定加減一、description 篩掉列或列數相同便宣稱對齊。
- 必須同時核對投球前 balls／strikes、半局、out／base 狀態及官方總投球數；不確定情況繼續排除。
- 不得因修正 Dataset A 而破壞 Phase 0 已驗證 Challenge 三欄 join；必要時使用獨立的版本化歷史對齊 adapter。
- 使用相同固定 20 場重新稽核，保留先前版本，不換場次；報告納入／排除變化與 RE 取樣影響。

## Comments

- 2026-09-18：使用者同意先測單場、再測批次。確認的測試介面為 `build_historical_dataset` 與 `run_historical_batch`；透過公開結果驗證，不測私有函式。保留固定 20 場、既有來源與舊報告，本輪不擴大全季下載或進行 WP 訓練。

## Answer

- 新增獨立 `historical-event-alignment-v1`，Dataset A 升為 v2；Phase 0 三欄 join 與 Challenge 邏輯未變。舊 Dataset A v1 可驗證與比較，不追溯宣稱已通過 v2 核對。
- 打席事件序列、兩來源判決類型、投球前後球數、半局、出局數與跑者身分／壘位皆核對；官方實際投球總數與既有比分稽核維持。未知碼、缺漏、矛盾或非唯一跑者路徑整場排除。
- 固定 20 場全數通過，共 5,748 球。補回原先排除的 5 場，原 15 場除新增對齊證據外，特徵、標籤與取樣欄位完全一致。
- 10 筆自動判決只留於 `games[].alignment.non_pitch_events`，不進入投球或 RE 樣本；14 球保留不同的 feed／Statcast 編號。一個完整無投球打席不生成 RE24 首球。
- 179 項測試通過，包含可攜式敬遠、起始／中途／終局計時器情境及批次快取驗證。兩次離線執行皆零下載，第二次重用 20 個分片，lock 一致。
- Train-only RE24 觀測數由 881 增至 1,188，RE288 由 3,423 增至 4,599；詳見 [驗證報告](../../../reports/archive/phase2/phase2_alignment_validation.md)。兩場平手邊界樣本不足，不能採用其 1.0 平均作正式估值。
- Issue 06 在固定工程樣本範圍完成；全季覆蓋、再見真實樣本及正式資料版本仍由 Issue 03 追蹤。本輪未 commit／push，`formal_training_ready=false`。
