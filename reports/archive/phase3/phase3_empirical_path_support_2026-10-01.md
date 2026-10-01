# Phase 3：歷史後續路徑、表外支持與正式策略閘門稽核

日期：2026-10-01。研究範圍仍是兩次制、第 1–9 局；本報告接續[合成策略原型](phase3_synthetic_regulation_policy_2026-10-01.md)，不把它升格為正式政策。

## 這次補上的部分

新增可重播的 `phase3_empirical_support` 稽核，將固定 91 場候選與額度感知 episode 逐筆一對一核對，並驗證來源指紋、歷史行動、到達間隔、額度終止、局數範圍及固定樣本分母。對每個候選只沿**實際發生的同隊後續暫定機會**，計數官方 WP ±5 分表內／表外、下一機會 WP 雙側支持，以及表外後返回表內。`actual_challenge` 僅用於事後分層，絕不作決策時特徵或因果效果。

| 切分 | 場數／候選 | 實際挑戰 | 下一機會已觀察 | 額度耗盡／九局設限 | 當前 WP 雙側缺值 | 表內起點、後續曾表外 | 表內起點、後續表外又返回 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 43／6,297 | 155 | 6,211 | 26／60 | 1,041 | 1,620 | 646 |
| Validation | 12／1,636 | 43 | 1,612 | 4／20 | 201 | 230 | 31 |
| Test | 12／1,828 | 57 | 1,804 | 6／18 | 249 | 339 | 65 |
| 名義 External | 24／3,371 | 112 | 3,323 | 14／34 | 581 | 961 | 321 |
| 合計 | 91／13,132 | 367 | 12,950 | 50／132 | 2,072 | 3,150 | 1,063 |

「後續曾表外」及「又返回」的單位是**起點候選**，同一場內會重疊計數，並非獨立路徑或機率質量；只檢查後續同隊暫定機會，不代表其間每一球。直接下一候選的表內→表外為 76 筆，表外→表內為 29 筆。這已足以否定「從未跨界」的簡化假設，但不能提供未選行動的跨界機率。Test 實際挑戰只占 57／1,828；即使粗分歷史兩臂，也不能由被選來挑戰的球與被保留的球之後續差異推論挑戰效果。先前 [12 格行動支持稽核](../phase2/dataset_b_action_support_and_censoring_2026-09-29.md)只有 2 格達預定最低雙臂門檻，亦未改變。

## 為何尚不能補成正式政策

1. **Legal 母體：**13,132 筆的 ABS 技術可用性及 replay 後資格仍全為 `unknown`；5 場官方挑戰無法定位的 Train 比賽仍整場排除。91 場已留存的 feed 線索稽核只有 3 場各 1 筆非 ABS `reviewType`（`MA`／`NH`），沒有可驗證的全場停用／恢復區間；這些代碼不能直接定位候選的 replay 後資格。官方說明確認：系統故障期間可暫停接受挑戰，replay review 後不能再提出 ABS Challenge；但目前快取的逐球來源沒有經驗證、覆蓋全場的停用／恢復區間與 replay 後逐球資格欄位。不能把「未看到文字線索」改成「可挑戰」。規則依據：[MLB ABS Challenge System 說明](https://www.mlb.com/news/abs-challenge-system-mlb-2026)。
2. **反事實轉移：**歷史資料只觀察到實際行動及其後續球序。另一行動可能改變球數、出局、打者、額度、下一個機會與整場路徑；不能複製同一條後續球序。Train 的行動支持過稀，且被挑戰球並非隨機選取。因此現有 hazard、下個狀態類別及本次返回比例都只能作觀察性診斷。
3. **表外 continuation：**官方 WP 只覆蓋特定分差區間；2,072 筆當前雙側缺值仍明示缺值。這次看見的返回不等於可估未來未觀察分支的機率，也不是表外勝率。不得截成 ±5、補 0／1，或用當場實際結果回填決策時價值。
4. **驗證：**2025 Test 不是官方固定 WP 快照的完全獨立樣本外資料；2026 僅是名義 External，正式 Legal 清冊與開發場隔離尚未全數核准。合成策略的內部價值差不能稱樣本外政策增勝。

所以下列閘門仍為 `false`：`formal_legal_opportunity_ready`、`counterfactual_transition_ready`、`empirical_outside_continuation_ready`、`formal_policy_evaluation_ready`。這不是程式未跑完，而是目前證據無法識別所需量。若要解除，需取得可逐球定位且能證明完整覆蓋的官方 ABS 停用／恢復及 replay 時序來源；在預宣告的 Train／Validation／Test／External 中建立兩行動的充分支持與反事實轉移設計；對 ±5 外狀態取得獨立估值或採明示未知區間的有限視野 estimand，並先鎖定驗收門檻。資料來源不足時可縮限研究問題，但必須事前定義且不能事後挑選容易估值的路徑。

## 重播與驗證

輸入為本機受 `.gitignore` 排除的候選、episode 與 Phase 2 收尾檔；其他 clone 不會自動擁有。最終程式版輸出 `data/processed/phase3_empirical_path_support_2026-10-01-v4.json` 與重播 `v5.json` 的 SHA-256 同為 `BC77194021FE07EDECD3C9CB279FBCE0CF36D583BDD279B1A1DE338D9E95046F`。程式版本與來源 manifest 已記於輸出，當前未提交的工作目錄不能追溯稱正式實驗。

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.phase3_empirical_support --preparation data/processed/dataset_b_population_preparation_2026-09-29-v13.json --episodes data/processed/dataset_b_resource_aware_episodes_2026-09-29-v5.json --phase2-closeout data/processed/phase2_closeout_2026-10-01-v4.json --output data/processed/phase3_empirical_path_support_replay.json
python -m unittest discover -s tests -v
```

若原始候選、episode、清冊或額度契約改變，程式拒絕沿用舊結果。報告數值僅屬固定樣本的歷史路徑描述，不是正式 Future Opportunity Model、Dynamic Policy 或 RRA。
全專案標準函式庫測試 300 項通過；新增測試涵蓋表外後返回、行動與到達不一致即停止、額度耗盡不當作右設限，以及不同隊伍不得串成同一條後續路徑。
