# Phase 2 非投球事件對齊驗證

日期：2026-09-18

## 結論與範圍

[Issue 06](../../../.scratch/phase2-models/issues/06-no-pitch-alignment.md) 的固定工程樣本驗收完成。使用原本 35 份來源、相同 10 個日期與 20 場比賽，Dataset A v2 納入 20 場／5,748 球；舊版為 15 場／4,303 球。沒有更換失敗場次、重新下載來源或覆寫舊報告。

原先通過的 15 場，除了新增 `alignment` 證據，逐球鍵、狀態、特徵、標籤與 RE 取樣欄位完全相同。新增納入的 5 場均為原先因非投球事件或編號偏移而排除的場次。Phase 0 的 Challenge 三欄 join 與額度邏輯沒有修改。

這是資料工程改善，不代表全季無偏、WP 已完成或正式 Dynamic Policy 可評估。`formal_training_ready` 與 `formal_policy_evaluation_ready` 維持 false。

## 修正與證據

- 對齊器 `historical-event-alignment-v1` 獨立於 Phase 0。逐打席核對完整事件順序、原始判決碼與 Statcast 判決類型、前後球數、上下半局、出局及跑者身分／壘位。
- feed 的 `isPitch=true` 實際投球仍與官方 `numberOfPitches` 核對；比分完整性與年度切分沿用既有稽核。
- 10 筆自動判決保存在 `games[].alignment.non_pitch_events`，不加入投球、RE24／RE288 或 ABS Opportunity 樣本。沒有真實投球的打席不補造 RE24 首球。
- 14 個實際投球的兩來源編號不同，輸出保留原始 Statcast `pitch_number`，另保存 `feed_pitch_number`、`statcast_pitch_number` 與 `feed_event_index`，不是以固定加減一取代證據。
- runner movement 依事件核對，可合併唯一的分段跑壘路徑、處理明確代跑與有實際移動證據的全空佔位列。第三出局後沒有可延續的壘包狀態。未知或歧義仍排除。
- 固定 feed 的觸身球 `H` 會將來源 `balls` 計數加一；用對應判決類型與測試核對，不將它誤認為自動壞球。白名單外的判決碼須另補來源驗證。

## 原先排除場次

| game_pk | 日期 | 新納入實際投球 | 非投球事件 | 兩來源編號不同的實際投球 |
|---|---|---:|---:|---:|
| 565047 | 2019-05-15 | 284 | 4 | 0 |
| 564888 | 2019-08-15 | 279 | 2 | 0 |
| 718158 | 2023-05-15 | 283 | 2 | 7 |
| 718159 | 2023-05-15 | 330 | 1 | 5 |
| 745015 | 2024-05-15 | 269 | 1 | 2 |
| 合計 | | 1,445 | 10 | 14 |

2019、2021、2022、2023、2024 各 4 場通過；實際投球數分別為 1,123、1,109、1,226、1,141、1,149。未讀取新 2025 Test 或 2026 External 來源作本次選型。

## RE 取樣影響

以下只以 Train 2019／2021–2023 重算；2024 不參與 RE 或邊界估計。對齊證據與判決類型不加入模型特徵。

| 項目 | 修正前 | 修正後 |
|---|---:|---:|
| Train 場次 | 12 | 16 |
| RE24 首個實際投球樣本 | 881 | 1,188 |
| RE288 實際投球樣本 | 3,423 | 4,599 |
| RE24 有觀測的格子 | 23／24 | 24／24 |
| RE288 有觀測的格子 | 230／288 | 247／288 |
| 忽略的非 Train 場次 | 3 | 4 |
| 九局平手場次 | 0 | 2 |

RE 樣本增加來自補回整場真實投球，不是將 10 筆自動判決當投球。仍有 41 個 RE288 格子沒有觀測，平均維持 null；所有格子出現觀測也不等於已可靠估計。

九局平手新增 `565047` 與 `718159`，兩場最終均主隊勝，開發平均因此為 1.0。**兩場不具統計支持，不能拿這個數值作正式 Regulation Boundary Value。** 此處只使用九局平手與真正終場勝負標籤，沒有延長賽投球特徵或 Challenge policy。

絕對分差 0–5：5,351 球／20 場；6–10：366 球／7 場；11+：31 球／1 場。同場可能跨分差組。大比分與再見半局仍缺乏足夠支持，不能宣稱 WP 可靠；固定樣本沒有真實再見半局，合成測試不代替真實覆蓋。

## 測試與重播

- 標準函式庫測試：**179 項通過**；新增 17 項單場對齊測試與 2 項批次測試。測試介面已由使用者確認為 `build_historical_dataset` 與 `run_historical_batch`。
- 案例涵蓋完整／中途敬遠、起始／中途／終局計時器事件、分段跑壘、盜壘、代跑、第三出局、觸身球，以及缺漏、矛盾、未知判決與衍生證據不一致。核心新增行為先確認測試失敗，再實作修正。
- `python -m compileall -q src tests scripts` 通過。
- 首次驗證：35 次快取命中、0 次下載、20 個新分片；第二次：35 次命中、0 次下載、20 個分片重用。
- 兩次開發 lock SHA-256 一致：`1b71ea28c5479c5bf518001342f83b92ab407de5facd95883553d82b03821fd5`。
- Python 來源集合指紋：`d691cac2a0745529ba62d9688ab46a055ab7fc2809c1c9f44cdaf00a7bfd3d3e`。
- 執行時基準 commit 為 `f9883721bcc9d62fcc999e6f36f5e8488e972b6c`，`worktree_clean=false`。修正尚未提交，不能說上述 commit 已包含新對齊器；程式指紋只供本輪開發重播。

本機產物皆在 Git 忽略的資料目錄：

- 新分片：`data/processed/phase2_alignment_2026-09-18/`
- 驗證報告：`data/processed/phase2_alignment_2026-09-18_verified.json`
- 重播：`data/processed/phase2_alignment_2026-09-18_verified_replay.json`
- 前後比較與完整 RE 格子：`data/processed/phase2_alignment_2026-09-18_verified_comparison.json`

新 clone 不包含這些快照。使用相同快取重播時，指定新的報告路徑；來源或程式版本不同時，指紋本來就應不同，不可硬改成相同值。

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m unittest discover -s tests -v
python -m abs_challenge.cli run-historical-batch --plan config/phase2_sample_plan.json --cache-dir data/raw/phase2_cache_2026-09-16 --artifact-dir data/processed/phase2_alignment_2026-09-18 --offline --output data/processed/phase2_alignment_next.json
python scripts/compare_historical_batches.py --before-report data/processed/phase2_batch_2026-09-16_report.json --before-artifacts data/processed/phase2_batch_2026-09-16 --after-report data/processed/phase2_alignment_next.json --after-artifacts data/processed/phase2_alignment_2026-09-18 --output data/processed/phase2_alignment_comparison_next.json
```

比較工具先驗證 lock、分片與 dataset 指紋，要求相同選樣及來源 manifests，再報告新納入、失去、未改變與有變動的既有場次，並重算 Train-only RE。不覆寫既有輸出。

## 下一步

Issue 06 在固定工程樣本範圍關閉；Issue 03 繼續處理跨月份覆蓋、未知型態排除率、真實再見及稀有狀態，再建立全季資料與正式版本。之後才進入 WP 訓練與校準。Dataset B 的 technical outage／post-replay-review 排除仍未完成，不因本輪進展解除正式 policy 評估限制。
