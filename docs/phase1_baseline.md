# Phase 1 Baseline 契約

## 定位

本階段只驗證資料及決策流程。自建 WP／RE、Future Opportunity 的估計與正式策略評估仍按產品規格留在後續階段。

## 公開介面與分工

| 模組 | 公開介面 | 責任 |
|---|---|---|
| `state_value.py` | `GameState`、`apply_call`、`counterfactual_states` | 純 called ball／strike 的狀態與終局處理 |
| `baseline.py` | `download_baseline_bundle`、`build_baseline_snapshot`、`SavantBaseline` | 固定來源、驗證完整度、查表與翻判價值 |
| `phase1.py` | `value_audited_challenges` | actual attempts 小樣本的支援性檢查與逐球報告 |
| `dynamic_prototype.py` | `solve_scenario`、`build_dynamic_demo` | 合成有限樹的精確向後求值 |
| `phase1_cli.py` | 由既有 CLI 註冊的新命令 | 檔案 I/O、Gate 指紋重驗、runtime manifest |

## 原始來源與 Snapshot

來源：[Baseball Savant Game Strategy Explorer](https://baseballsavant.mlb.com/game-strategy-explorer)。Adapter 使用官方頁面公開 JavaScript 的查詢方式，以 `Accept: application/json` 取得回應。

- `savant-explorer-bundle-v1`：保存頁面、公開 JavaScript、RE288 與八個壘包 WP 查詢的原始文字。每份來源內嵌 URL、query、UTC time、SHA-256、byte length、row count。
- `savant-baseline-v2`：正規化 288 個 RE 狀態、5,184 個含球數 WP 狀態。每個 WP 狀態有主隊分差 −5 到 +5 的 11 個機率，共 57,024 個值。v1 有來源視角錯誤，程式已拒絕讀取。
- `source_page_seasons` 是頁面宣告的 2016–2025；`re_response_years` 保留回應列的 2025。不能自行認定兩種年份語意相同，也不能稱作獨立的 2025 樣本外評估。
- `source_wp_perspective=batting`、`wp_perspective=home`：原始 `bat_wins_*` 是打方分差／打方勝率，上半局需同時反轉分差欄與取機率補數，下半局不變。`perspective=home` 請求在本次查核並未讓回應完成這個轉換；新下載明確請求 `bat`。見 [ADR-0001](adr/0001-savant-probability-perspective.md)。
- 所有缺值、越界、重複、非有限數與不相符的來源參數明確報錯；沒有分差截尾或插補。
- 原始與衍生資料不納入 Git；測試採合成完整表格及小型官方摘錄，不依賴下載資料。

## 狀態與估值

`GameState`：`inning` 1–9、`half` top／bottom、`outs` 0–2、`bases` 0–7、`balls` 0–3、`strikes` 0–2、非負 `home_score`／`away_score`。壘包位元 1／2／4 分別表示一／二／三壘有人。缺少壘包欄與明確無人不能混淆。

`CallTransition`：

- `next_state`：未終止時下一個可估值狀態。
- `terminal`：`home_win`、`away_win`、`regulation_tie` 或 `null`。
- `runs_scored`：此判決立即造成的得分。
- `half_ended`：是否出現原半局第三出局。
- `re_*`：原半局判決後狀態，供 RE288 使用，不與換邊後的對手 RE 混用。

`SavantBaseline.value_call` 分別估值原判維持 `s0` 與判決翻轉 `s1`。Decision Team 由原判及原半局決定，換半局後不改變。`delta_wp_decision` 是 0–1 機率單位的差，`delta_wp_percentage_points` 是百分點。它們是分析產物，不是 decision-time predictor。

RE 採未依再見截斷的半局表格：立即得分加上原半局剩餘 RE；第三出局後剩餘 RE 為零。再見保送在 WP 為勝率 1，在靜態 RE 比較仍保留未截斷半局慣例，因此 RE 不可解讀為該場實際還會得到的分數。

`savant_static_threshold` 使用 `0.2 / (0.2 + run_value_decision)`，只在正向 run value 時輸出。這是固定成本基準，不是 Dynamic RRA。

## 九局平手

`savant-regulation-tie-home-v1` 的主隊值為 **0.5**。來源是同份官方快照中第 10 局上、0 出局、二壘有人、0–0 球數、平手的 `bat_wins_0`，取補數轉為主隊值。這是從來源取得的外生值，不是默認每種比賽都五五波，也不是把比賽結束。

只有九局下第三出局且平手時使用它；九局上第三出局平手仍需打九局下。未生成第 10 局決策或補充額度，未模擬延長賽策略。Phase 2 才重估歷史邊界值。

## 小樣本報告與禁止外推

輸入 audit 必須屬於已通過的 Phase 0 Gate snapshot；CLI 驗證 Gate 依賴的 hash 並重算 Gate。feed 必須符合 audit 原始 manifest；相容 Phase 0 本機 raw bytes 與即時下載 canonical JSON 兩種 hash 語意。

逐球狀態：`valued`、`missing_baseline_state`、`unsupported_compound_event`、`invalid_state`、`excluded_extra_inning`。`valued` 只表示查表完成，不代表反事實因果效果已驗證；`valuation.warnings` 非空也會阻擋整批完整通過。

同球盜壘、暴投、捕逸、不死三振等不能僅由翻轉判決推得另一條路徑；有可辨識複合事件就排除。即使沒有此類旗標，也只是在純判決假設下的原型，不代表正式 Legal population 已完成。

原型使用過的 2026 開發樣本 `823244`、`823569`、`825027` 應標記為開發稽核樣本，後續正式 external evaluation 不用這三場作獨立成效證據。不得以目前結果調整正式模型超參數後再把同批資料稱作未見測試。

## 合成 Dynamic 範圍

有限情境樹使用指定的成功機率及同一 Decision Team 的葉節點 WP。成功保留、失敗扣一，零額度只能維持原判；每個分支可以有不同未來節點，不是單純固定門檻搜尋。

CLI 示範固定對手不挑戰，成功機率 0.6，假設每分支下一球為 called strike 機會，兩個機會後以官方 WP 承接。這些都是明示假設，未從資料估計 arrival 或球員信心，沒有使用真實測試比賽的未來球序。

## 可重現性與限制

報告內含 baseline／audit／feed／Gate hash、Python 版本與程式檔 hash。沒有本專案可用 commit SHA，或 worktree 不乾淨時，`formal_experiment_version_ready=false`。程式檔 hash 只供原型比對，不取代正式實驗版本基準。

目前所有輸出維持 `formal_policy_evaluation_ready=false`。視角問題已修正；使用者已同意 ±5 分限定原型驗收，見 [覆蓋與最終驗收 Issue](../.scratch/phase1-baseline/issues/05-baseline-coverage.md)。自建模型及大比分可靠度由 [Phase 2](phase2_dataset.md) 接續。
