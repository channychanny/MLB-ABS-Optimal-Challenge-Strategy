# Phase 3 第一輪：九局內假設式動態策略與額度價值

日期：2026-10-01。這是接續[Phase 2 限定收尾](../phase2/official_wp_phase2_closeout_2026-10-01.md)的**可重播、完整九局視野的合成模型原型**，不是已從 ABS 歷史資料識別的反事實轉移、正式 Dynamic Policy、球員翻判預測器或實際增勝評估。舊 Phase 1 的兩機會合成樹與[單步情境比較](policy_scenario_prototype_2026-09-30.md)保留；本輪新增跨剩餘局數倒推、0／1／2 額度、假設式 RRA 與固定 cohort 比較。延長賽策略不在本輪。

## 模型契約與倒推

來源固定官方 WP 的當前判決分支 `S0`／`S1`，轉成 Decision Team 視角。只對兩側 WP 均支援的純判決候選求值；其他候選回傳 `unsupported`，不把真實分差截成 ±5、不補零。決策時只讀判決前 Game State、原判及剩餘額度；歷史 `actual_challenge`、`overturned`、`post_action_budget`、到達標籤和事後球序不作預測特徵。

為能完整倒推到九局，模型**人工**假設：從當前局到第九局，每局最多一個「未來不利判決機會槽」；該槽以預設 `q_i` 機率出現。若出現而不挑戰，決策方基準 WP `W` 變為 `(1−ρ)W`；若挑戰並成功，恢復 `W`，失敗則維持不利判決並扣一次額度。未來翻判率 `p_f` 亦為情境假設。未來沒有真實比分、壘包、出局或對手挑戰狀態；它是 WP 尺度的合成資源模型，**不是**完整 Game State 轉移模型。勝負或九局平手的當前終局分支直接停止，使用既有版本化邊界。

令 `F_i,c(W)` 為從第 `i` 局後續機會開始、剩 `c` 次挑戰的情境價值；九局後 `F_10,c(W)=W`。對每個機會，`save=F_{i+1,c}((1−ρ)W)`，`challenge=p_f F_{i+1,c}(W)+(1−p_f)F_{i+1,c−1}((1−ρ)W)`；`dynamic` 取兩者較大，`never` 永不挑戰，`fixed_confidence` 在翻判率達 0.5 時挑戰。無機會時沿原 `W` 進下一局。程式以無量綱係數自九局倒推，因此所有合成葉值保持 0–1，不需裁切 WP。

當前判決的 `Q_save=F_i,c(WP(S0))`；`Q_challenge=p F_i,c(WP(S1))+(1−p)F_i,c−1(WP(S0))`，其中 `p` 是**當前**人工成功率，與固定的未來 `p_f` 分開。對額度 0／1／2 均計算目前決策的 `V(S,c)`；在固定未來情境下解出使兩個 Q 相等的門檻。這是 **synthetic RRA**，不是已校準球員所需辨識準確率。成功分支保留 `c`，失敗分支才變 `c−1`；額度 0 沒有挑戰選項。

## 預先宣告的敏感度格點

規格見 [`phase3_synthetic_policy.json`](../config/phase3_synthetic_policy.json)。目前的三組數字都是用來觀察政策翻轉的**人工假設**，不是 Dataset B 到達模型估計，也不是可信上下界：

| 情境 | 每局機會機率：1–3／4–6／7–9 | 不利判決損失比例 `ρ` | 未來翻判率 `p_f` |
| --- | --- | ---: | ---: |
| 稀疏小損失 | 0.10／0.15／0.20 | 0.02 | 0.50 |
| 中等 | 0.25／0.35／0.45 | 0.04 | 0.50 |
| 後段較多 | 0.10／0.25／0.65 | 0.06 | 0.50 |

當前 `p` 格點為 0.25、0.50、0.75、0.90。固定門檻基準只看 `p≥0.50`，不衡量當前 WP 差或剩餘額度；因此在 `p=0.50` 時它會對全部可估候選建議挑戰。`never` 永不挑戰。三種政策在**各自一致的合成未來規則**下倒推；`dynamic` 的模型內部價值不低於另兩者是最佳化定義的一部分，不是從真實勝負驗證出的優勢。

## 固定 91 場盤點

同一固定 96 場清冊中 91 場有完整來源，5 場整場排除且不替補；13,132 筆第 1–9 局有額度暫定候選中，11,060 筆兩側官方 WP 可估，2,072 筆 abstain。Train 43 場／6,297 筆、Validation 12／1,636、Test 12／1,828、名義 External 24／3,371。ABS 停用／replay 資格仍全部未知，故這不是完整 Legal population，也不能把名義 External 稱正式政策 holdout。

下表只取人工當前翻判率 `p=0.50`，分母為各 split 雙側可估候選；數字是模型**建議次數**，不是歷史實際挑戰、實際成功或增加勝場：

| 切分 | 可估／暫定候選 | 稀疏小損失：動態挑戰 | 中等：動態挑戰 | 後段較多：動態挑戰 | 固定門檻挑戰 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 5,256／6,297 | 4,916 | 3,353 | 2,406 | 5,256 |
| Validation | 1,435／1,636 | 1,401 | 977 | 688 | 1,435 |
| Test | 1,579／1,828 | 1,521 | 1,095 | 772 | 1,579 |
| 名義 External | 2,790／3,371 | 2,642 | 1,752 | 1,246 | 2,790 |

在同一 `p=0.50` 的三情境內，Test 的 1,579 筆可估候選有 772 筆始終建議挑戰、58 筆始終保留、749 筆隨人工未來假設改變；另 249 筆不支援。名義 External 對應為 1,246／148／1,396 筆，另 581 筆不支援。這裡的「始終」**只限所列三個人工情境與單一 p**，不是對所有合理未來模型穩健。

Test 的中等情境下，模型可定義門檻的 1,559 筆候選，其 synthetic RRA 中位數約 0.371；名義 External 為 2,726 筆、中位數約 0.397。Test 改用稀疏小損失／後段較多情境時，中位數約為 0.080／0.505。這個巨大變動恰好說明未來機會假設尚未由資料識別；**不能**把 0.371 當成球員實務上應採用的準確率門檻。輸出另保留進攻／防守方、局數階段及剩餘額度分組，並將無正向挑戰價值者標為無嚴格門檻。

## 單一狀態輸入

除固定 cohort 外，命令也能讀取既有[`policy_scenario_example_state.json`](../config/policy_scenario_example_state.json)：五局下、1 出局、一壘有人、2–1、平手、原判好球、剩 1 次。手填輸入必須明示 `assume_pure_called_pitch=true`；若同球有額外跑壘，這項假設不成立，不能把輸出當作該球的完整轉移。官方快照給 `WP(S0)=0.563`、`WP(S1)=0.588`。在人工 `p=0.50` 下，稀疏小損失／中等情境選挑戰，後段較多情境選保留；其 synthetic RRA 約為 0.145／0.384／0.515。輸出逐情境列出 `Q_save`、`Q_challenge`、`V(S,0/1/2)`、RE 與缺值原因。這些 `V` 已包含人工未來不利判決損失，不應與官方原始 WP 當同一個經驗估計量比較。

## 防洩漏、重播與未過閘門

批次執行前重驗 Phase 2 收尾結果、91 場候選檔與固定情境 cohort 的 SHA／逐筆官方 S0／S1；任何來源變動應停止，不能悄悄沿用舊評估。最終單一狀態輸出為本機 `data/processed/phase3_synthetic_example_2026-10-01-v2.json`（SHA-256：`B3E797D2E5232A2B989EDB757AD9DE14B6BC8A789BB451ADD2BD4DD1C90B2FA1`）；批次 `v6.json`／`v7.json` 兩份重播相同（SHA-256：`067F6C9B73BFDFEBC867F60AC54165B7AADB6D66E33298BF0ED1A7EBAB845041`）。每次執行須用新檔名並保存實際程式指紋。在有相同本機來源快取的專案根目錄重播：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.phase3_synthetic_policy --state-input config/policy_scenario_example_state.json --output data/processed/phase3_synthetic_example_replay.json
python -m abs_challenge.phase3_synthetic_policy --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --baseline-result data/processed/dataset_b_observational_baseline_2026-09-29-v3.json --cohort-result data/processed/policy_scenario_cohort_2026-09-30-v4.json --phase2-closeout data/processed/phase2_closeout_2026-10-01-v4.json --output data/processed/phase3_synthetic_policy_replay.json
python -m unittest discover -s tests -v
```

標準函式庫測試 295 項通過，涵蓋手算倒推、成功／失敗額度、終局、額度單調、無正向價值、主客視角、表外拒估、契約防升格及歷史實際行動／結果標籤不影響建議。工作目錄仍有未提交變更，因此此重播不是乾淨 commit 的正式實驗。來源檔與輸出受 `.gitignore` 排除，其他 clone 不會自動取得。

`formal_legal_opportunity_ready=false`、`counterfactual_transition_ready=false`、`empirical_outside_continuation_ready=false`、`formal_policy_evaluation_ready=false`。WP-only 人工未來模型無法知道未來真實比分何時超過官方 ±5、又何時回表；現有[合成跨界契約](../phase2/official_wp_continuation_contract.md)仍是這類路徑的獨立安全檢查，不能因本輪數值可算就視為實證 continuation。官方 WP 可能已內含某些歷史行為效果，人工未來損失與其是否重複計值未證明。完整下一 Game State、對手策略、決策前可用成功率、來源資格與以比賽為單位的正式政策績效仍是下個研究閘門；本輪沒有宣稱正式 Phase 3 完成。
