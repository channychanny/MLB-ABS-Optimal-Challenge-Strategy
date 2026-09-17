# Phase 1 官方 Baseline 原型報告

更新日期：2026-09-15  
狀態：**2026-09-15 使用者同意以官方 ±5 分覆蓋作限定原型驗收，Phase 1 此範圍已完成；不代表全比分或正式策略已完成。**

## 已完成

- 官方 RE288、含球數 WP 與方法頁／JavaScript 原始回應的固定快照及來源 manifests。
- 純好壞球的兩種判決狀態、保送強迫進壘、擠回分、三振、換邊、免打九下、再見及九局平手。
- Decision Team 視角的兩條路徑查表與差值；不使用 observed delta 代替反事實。
- 真實 Phase 0 樣本估值 CLI、原始 feed 與 Gate 指紋驗證、異常狀態報告。
- 合成有限情境樹的 0／1／2 額度決策流程；不是已訓練模型或正式策略。
- 103 項標準函式庫測試（既有 56 項＋新增 47 項）。測試不需網路或本機下載資料。

## 官方 Snapshot

| 項目 | 結果 |
|---|---|
| 來源 | Baseball Savant Game Strategy Explorer |
| 頁面宣告期間 | 2016–2025 |
| RE 回應列 `year` | 2025；與頁面期間分別保存 |
| RE 狀態 | 288 |
| Regulation 含球數 WP 狀態 | 5,184，每個含 11 個分差值 |
| 分差範圍 | 主隊 −5 至 +5，不截尾、不外推 |
| 九局平手主隊邊界 | 0.5，版本 `savant-regulation-tie-home-v1` |
| v2 快照 SHA-256 | `834dab0f7ef6a394e8131d9aaf5fef8e9b26a9ac2b0abffddcb248bf7b40f8a2` |

本機原始 bundle 為 `data/raw/savant_baseline_2026-09-14.json`，修正後正規化為 `data/processed/savant_baseline_v2_2026-09-15.json`。從同一 bundle 離線重建的 `_replay.json` 與正規化檔案 SHA-256 完全一致。這是固定來源可重播的證據，不是模型品質證據。

來源：[官方頁面](https://baseballsavant.mlb.com/game-strategy-explorer)。頁面與 RE 列年份不同，不能推定其完整估計窗口，也不能用此 snapshot 宣稱獨立 2025 test。

## 真實小樣本

沿用已通過 Phase 0 的三場 MLB：`823244`、`823569`、`825027`，共 16 次 actual attempts。未新增抽樣以掩蓋失敗案例。

| 檢查 | 結果 |
|---|---:|
| 兩種狀態可查表 | 12 |
| 超出分差範圍 | 4 |
| 可查表但負向翻判價值警示 | 0 |
| 整批狀態 | `partial_smoke_test` |
| CLI exit code | 1 |
| 正式 Policy Evaluation 就緒 | false |

4 次缺值全部來自 `825027` 的後段大比分狀態，未以 ±5 分或 observed WP 補值。12 次修正後查表差值為 +0.2 至 +11.3 個百分點；這只是固定外部模型的兩狀態差值，**不是已驗證的 ABS 因果效益或策略成效**。

本機目前可用報告為 `data/processed/phase1_values_v2_2026-09-15.json`。另外，兩場完整落在官方表格範圍內的 `823244`／`823569` 合計 10 次挑戰，已由相同命令回傳 `complete_smoke_test`／exit code 0，輸出為 `phase1_supported_games_v2_2026-09-15.json`；這不取代原三場的部分結果，也不隱藏另外四次缺值。

舊 `savant-baseline-v1` 與 `phase1_values_current.json` 等 v1 衍生檔保留作錯誤診斷紀錄，**不再可用於研究**；所有產生資料均受 `.gitignore` 排除。

## 已修正：來源打方視角誤讀為主隊視角

最小例子：四局上、0 出局、無人在壘、主隊落後 5 分，將原本第一顆 called strike 翻為 ball。

| 兩種判決後狀態 | 原始打方 +5 分勝率 | 正確轉換後主隊勝率 |
|---|---:|---:|
| 0 壞 1 好 | 0.920 | 0.080 |
| 1 壞 0 好 | 0.922 | 0.078 |

v1 錯把 `bat_wins_minus_5` 當成主隊落後 5 分的主隊勝率，讀到 0.077／0.081，造成客隊差值 −0.4 個百分點。2026-09-15 比對原始回應、上下半局球數／跑者方向與 Statcast 主隊基準，確認應以打方分差與打方機率解讀；上半局反分差並取補數後，例子為客隊 +0.2 個百分點。`home`／`bat` 請求在本次觀察未改變回應，不能只依請求值推定已完成轉換。

診斷依 `diagnosing-bugs` 流程，先以單一狀態重現，再建立兩個轉換回歸測試並確認失敗，修正後通過；原三場的 12 次查表已零方向警示。原始資料沒有修改，修正的是本地 adapter，不應再將暫時診斷稱為官方模型異常。小型來源摘錄在 `tests/fixtures/savant_explorer_excerpt.json`，決策記錄在 [ADR-0001](../docs/adr/0001-savant-probability-perspective.md)。

## 合成 Dynamic 原型

本機 `data/processed/phase1_dynamic_v2_2026-09-15.json` 已跑通。只驗證精確向後求值、成功保留、失敗扣額度及兩條分支使用不同後續狀態。對手固定不挑戰，成功機率 0.6 是假設，不是訓練結果；兩個機會後由官方 WP 承接。

不將此處 `value` 當成實際比賽預測，不產生正式 RRA 或增加勝場的宣稱。一般 public solver 另有手算測試，驗證「只有一次時保留、兩次時改為挑戰」以及成功後仍可挑戰下一次。

## 尚未完成與下一步

1. 視角轉換已由 [Issue 04](../.scratch/phase1-baseline/issues/04-wp-source-quality.md) 關閉；後續來源更新仍需回歸檢查。
2. **已確認以官方 ±5 分覆蓋作限定驗收**；4 次大比分仍維持缺值，不擅自截尾。見 [Issue 05](../.scratch/phase1-baseline/issues/05-baseline-coverage.md)。
3. 已進入產品規格 Phase 2 的自建 RE／WP 工作；先建置 Dataset A 與 RE 開發流程，WP 校準尚未完成。不得將官方 snapshot 的資料窗口混成模型訓練切分。
4. 正式模型前仍需 Legal Opportunity 的 technical outage／post-replay-review 排除、完整樣本覆蓋及專案 commit SHA。
5. 本輪 2026 三場維持開發稽核樣本身分，後續不作獨立 external 成效證據。

本次沒有重新初始化 Git、建立 commit、覆寫既有資料或研究延長賽挑戰策略。
