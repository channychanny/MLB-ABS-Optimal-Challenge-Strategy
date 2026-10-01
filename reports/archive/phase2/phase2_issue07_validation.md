# Phase 2 擴大樣本對齊修正驗證

日期：2026-09-19

## 結論

Issue 07 在固定工程樣本範圍完成：沿用相同 30 個日期、84 場比賽及 117 份來源，84 場全數通過，共 24,448 顆第 1–9 局實際投球。原先排除的 14 場全部恢復，沒有替換場次或重新下載來源。

原先通過的 70 場，其完整 `dataset_content_sha256` 不變，特徵、標籤及既有對齊證據均保持一致。這不是全季資料或正式 WP 模型完成；Issue 03 仍需全季覆蓋、排除偏差及正式版本鎖定。

## 修正語意

- `P / Pitchout` 對應 Statcast `pitchout`，保留為實際投球，來源球數增加一顆壞球。
- `M / Missed Bunt` 對應 `missed_bunt`，保留為實際投球，來源好球數加一。兩者都仍核對判決類型、前後球數、出局、跑者及官方投球總數。
- `type=no_pitch` 不再一律解讀為 CSV 自動好壞球列。明確 `isPitch=false`、`details.code=N`，且無 `call`／投球編號／投球資料的事件，只有在球數不變、出局旗標與該事件跑者出局證據一致時才識別為 feed-only。
- feed-only 事件保留於場次的選用欄位 `alignment.feed_only_events`，不產生 CSV 列、投球或 RE 樣本。完整事件狀態重建仍執行跑壘，因此沒有忽略盜壘失敗、犯規或失誤的後續狀態。
- `non_pitch_events`／`non_pitch_rows` 繼續只表示有 CSV 對應的自動判決，與 feed-only 分開。未知碼、矛盾、缺失的實際投球或多出的 CSV 列仍整場排除。
- Dataset A v2 與 alignment v1 的既有欄位保持相容，新增欄位只在實際有 feed-only 事件時輸出。來源及程式指紋區分此次建置，不把舊資料自動升級。

本輪共有 50 筆 CSV 自動判決列、50 球兩來源編號不同、5 筆 feed-only 事件，以及 7 個無實際投球的打席紀錄。feed-only 事件分布於 `565032`（第 34 打席）、`565450`（66）、`565197`（36）、`661116`（60）、`745106`（12）。其中 `565032` 的 N 事件是修正第一個 pitchout 阻擋後才出現的後續型態；不能只按原先第一個錯誤計數推定事件總數。

`745106` 第 12 打席由一壘跑者盜壘失敗完成第三出局，整個打席紀錄沒有投球，故不生成首球 RE 樣本。其他 N 標記附近的 action 仍按來源重建；`565197` 的失誤得分也未被刪除。

## 前後比較

| 項目 | 修正前 | 修正後 |
|---|---:|---:|
| 選定場次 | 84 | 84 |
| 通過／排除 | 70／14 | 84／0 |
| 實際投球 | 20,234 | 24,448 |
| Train 場次 | 56 | 69 |
| Validation 場次 | 14 | 15 |
| Train RE24 樣本 | 4,170 | 5,170 |
| Train RE288 樣本 | 16,308 | 20,229 |
| RE288 有觀測格子 | 280／288 | 282／288 |
| 再見截斷半局所屬場次 | 2 | 3 |
| Train 九局平手場次 | 8 | 9 |

2019／2021／2022／2023／2024 分別納入 18／15／18／18／15 場、5,265／4,484／5,204／5,326／4,169 球。新增投球總數為 4,214。

三場再見為 `565809`、`634085`、`661583`；其截斷半局共 50 顆投球保留 WP 標籤，RE 為 null。RE288 仍有 6 格沒有觀測，不能填零。15 場 Validation 不參與 RE 或九局平手邊界估計。

九局平手 Train 為 9 場、6 場主隊勝，開發平均 2／3；新增 `717389`。樣本不足且跨年度，不作正式 Regulation Boundary Value。本研究仍只建模第 1–9 局的挑戰策略。

| 分差絕對值 | Train 球／場 | Validation 球／場 |
|---|---:|---:|
| 0–5 | 17,783／69 | 3,851／15 |
| 6–10 | 2,437／26 | 318／5 |
| 11+ | 59／3 | 0／0 |

同場可跨分差組。Train 分差範圍 −11 至 +11，Validation −4 至 +10。11+ 分仍只有 3 場 Train，Validation 無支持；不能宣稱大比分 WP 已可靠。2025 Test／2026 External 未用於本輪修正或選型。

## 測試與重播

- TDD 經公開 `build_historical_dataset` 介面重現差異，先確認失敗再修正；新增 7 項測試，整套 **192 項通過**。
- 新案例包含兩種實際投球判決、feed-only 跑者移動、無投球第三出局、未知／矛盾事件與 CSV 缺漏、出局旗標缺證據，以及重新計算 hash 後仍不合法的衍生證據。
- 最終版本第一次離線建置：117 次快取命中、0 次下載、84 個新分片。
- 第二次離線重播：117 次命中、0 次下載、84 分片重用；lock 一致。
- 開發 lock：`56e81a15d42862ddee183fb781b11a84fa53e26a19693d975a292c94ea573d6c`。
- 程式集合指紋：`f1107040bec385aad510d82f90f4b3df4627a7db5702441865c8625127b85559`。
- 執行版本基準為 `f9883721bcc9d62fcc999e6f36f5e8488e972b6c`，工作目錄未提交，Python 3.14.6、standard library。此 SHA 不包含未提交修正；所有結果仍屬開發驗證。

兩個原固定日期（2021-07-15、2024-07-15）仍無候選賽事，故現行批次 exit code 1、`complete_selected_sources=false`；所有 84 個已選定場次均接受，沒有下載失敗或稽核排除。此狀態不應被誤讀成所有日期都有比賽。

## 重現指令與本機產物

以下使用新輸出檔名，不覆寫既有報告；原始快取及分片受 Git 忽略，新 clone 需另取得。

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m unittest discover -s tests -v
python -m abs_challenge.cli run-historical-batch --plan config/phase2_expanded_sample_plan.json --cache-dir data/raw/phase2_cache_2026-09-16 --artifact-dir data/processed/phase2_issue07_2026-09-19 --offline --output data/processed/phase2_issue07_next.json
python scripts/compare_historical_batches.py --before-report data/processed/phase2_expanded_2026-09-18_network_report.json --before-artifacts data/processed/phase2_expanded_2026-09-18_network --after-report data/processed/phase2_issue07_next.json --after-artifacts data/processed/phase2_issue07_2026-09-19 --output data/processed/phase2_issue07_comparison_next.json
python scripts/summarize_historical_coverage.py --report data/processed/phase2_issue07_next.json --artifacts data/processed/phase2_issue07_2026-09-19 --output data/processed/phase2_issue07_coverage_next.json
```

本輪報告前綴為 `data/processed/phase2_issue07_2026-09-19_`，後綴依序為 `verified.json`、`replay.json`、`comparison.json`、`coverage.json`；`probe.json` 是強化出局旗標檢查前的開發探測，不作最終版本。原批次與原報告保留。

## 下一步

Issue 07 固定樣本驗收完成，回到 Issue 03 的全季下載規模／資源評估及正式資料版本。84 場全數通過只支持目前工程樣本；全季排除偏差、稀有狀態與乾淨版本仍需驗證。WP 校準、Dynamic Policy 與 RRA 未完成，Dataset B 的 Legal Opportunity 排除缺口仍獨立追蹤。
