# 官方 WP 覆蓋檢查：第一輪開發樣本

日期：2026-09-21。Issue 01 **部分完成**，不是完整機會母體驗收，也不是正式策略評估。

2026-09-22 更新：五球出局數差異已證實為終局逐球 count 延遲，修正後為 22／29；完整六場機會母體檢查亦已完成。見 [後續報告](official_wp_opportunity_coverage.md)。以下保留第一輪原始結果，不作目前數值。

## 固定樣本與母體

執行前保存 [計畫](../config/official_wp_coverage.json)：本機六場既存 2026 MLB feed 全部納入，不依本輪結果挑場。這是便利開發樣本，其中三場曾用於 Phase 1，不能稱前瞻抽樣或獨立外部測試。全部六場重新解析為 confirmed 的 mlb-2026 兩次／成功保留制度，重新以原始 feed 與 ABS CSV 建立 audit，均通過單場檢查。

本輪預先採「固定實際挑戰樣本必須 100% 支援才能稱全部可估值」的工程門檻；不是整季覆蓋率的統計驗收門檻。

| 比賽 | 日期 | 第 1–9 局挑戰 | 兩側可估值 |
|---|---|---:|---:|
| 823244 | 2026-03-25 | 1 | 1 |
| 823488 | 2026-03-28 | 2 | 1 |
| 823569 | 2026-04-04 | 9 | 9 |
| 824134 | 2026-04-04 | 6 | 2 |
| 824378 | 2026-04-04 | 5 | 2 |
| 825027 | 2026-04-04 | 6 | 2 |

## 結果

共 32 次 actual attempts；3 次延長賽另列，主要分母為 29 次。

- S0／S1 都支援：17 次（17／29，58.62%）。
- 單側支援：0 次。
- 兩側都超界：7 次，保留缺值及兩側 RE，不截尾。
- 純判決估值不支援：5 次，全部原因是「官方球後出局數與純判決不符」。這是保守一致性檢查結果，不代表已證實五球都有實際複合跑壘；需再診斷來源／狀態語意。
- 無效狀態：0 次；可估值列的負向價值警示：0 次。
- 進攻方 6／13 可估值；防守方 11／16。樣本很小，不能比較兩方的普遍策略價值。

只限通過純判決檢查的 24 次時，查表支援為 17／24；這是條件比例，不能替換主要分母的 17／29。原 Phase 1 三場仍為 12／16 支援、4 次超界，沒有將既有缺值改成成功。

JSON 另按年度、regime、比賽、Decision Side、局數、真實主隊分差與 count 保存分組結果。終局與九局平手的分支計數獨立列出；本樣本沒有此類分支，相關情境以合成測試驗證。

## 尚未完成與不能外推之處

- 本機這三日缺完整逐球 CSV，僅有 ABS-only CSV。本輪未執行下載；provisional opportunity population 尚未估值，其覆蓋率為 null，而不是 0 或 58.62%。
- 這批來源本身來自先前挑戰資料開發，仍有選樣偏差；即使日後補齊六場逐球資料，也不能稱整季代表性樣本。
- 尚未驗證 2024 兩次制度及 2025 Triple-A 的主線覆蓋；2023 三次制度不混入兩次核心分母。
- 尚未完成 technical outage／post-replay-review 排除，維持 provisional_source_limitations。
- 未來分支跨出 ±5 後返回的 continuation 尚待 Issue 03。當前查表覆蓋不等於正式 Dynamic Policy 支援。
- 本輪 research_support_gate_pass 與 formal_policy_evaluation_ready 均為 false，Issue 01 維持 claimed。

下一個增量：補齊明示 cohort 的完整逐球來源、建立並核對未挑戰事件母體；另診斷五次出局數不符。擴大抽樣前需先鎖定不依 actual attempts 篩選的完整比賽清單及覆蓋門檻。

## 重播與驗證

新命令不覆寫既有輸出，無網路請求：

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"
python -m abs_challenge.wp_coverage --plan config/official_wp_coverage.json --output data/processed/official_wp_coverage_new.json
```

exit code 1 代表已產生開發子母體報告、整體閘門未通過；2 表示計畫／基準／輸出錯誤。單場來源失敗保留在 games，並標示逐球分母不完整。無挑戰場次不因無事件被刪除，但需官方零次 counter 一致才能標為 zero_attempts；這不是沒有 opportunity 的證據。

本機輸出：

- data/processed/official_wp_coverage_development_2026-09-21_verified.json
- data/processed/official_wp_coverage_development_2026-09-21_replay.json

兩次離線 content lock 一致：`9969e41139cfde7eaf88475e66d5744e1d0b898e5f7b0e1122c900990b8c9800`。

- 計畫 SHA-256：`a03374f7b4bf77d36ddb2cc83da181fae36797ecdd5c5b7259dc8918db75cdf1`
- 官方 v2 SHA-256：`834dab0f7ef6a394e8131d9aaf5fef8e9b26a9ac2b0abffddcb248bf7b40f8a2`
- 規則 SHA-256：`31e65f33e130db029c5b5bc680faa4ac33d477a30d642bab58512b5f11077198`
- 執行 HEAD：`f9883721bcc9d62fcc999e6f36f5e8488e972b6c`；worktree_clean=false，新增程式尚未提交，所以僅為開發結果，不是該 commit 的正式實驗。
- JSON 保存輸入檔 hash、byte length、實際命令、Python 版本與程式檔 manifest；既有 raw 來源及 baseline 內嵌來源 manifest 保留。不能從本輪檔案 hash 推定新的下載時間。
- 完整標準函式庫測試 **208 項通過**，含新增 9 項：±5 跨界、RE 保留、終局／九局平手、攻守視角、換邊、複合／無效狀態分母、防洩漏與來源缺失重播。

本機原始及衍生資料仍由 Git 排除，新 clone 不含這些資料；需取得相同快照才能重播相同 content lock。
