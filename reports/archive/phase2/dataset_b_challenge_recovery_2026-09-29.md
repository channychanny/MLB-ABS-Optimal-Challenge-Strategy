# Dataset B 缺漏挑戰復原與限定模型輸入閘門

日期：2026-09-29。本報告接續 [2026-09-24 的 85／96 場工程準備結果](dataset_b_pretraining_preparation_2026-09-24.md)，不覆寫當時結論。固定的 96 場賽程選樣與 Train／Validation／Test／External 時間窗未變；沒有依挑戰結果補場。

## 11 場官方計數不符的查證

先以官方 feed 逐一核對全部 `reviewDetails`、打席結果文字、挑戰分隊及終場 `gameData.absChallenges`。缺漏不是解析器漏掉既有 review 欄位。再以 Savant ABS-only CSV 的三鍵 `game_pk`、一基底打席編號、`pitch_number`，對完整逐球 CSV 與 feed 做整場嚴格對齊。只有 ABS-only 比 feed 多出可唯一定位的投球，且補入後各隊成功／失敗數、挑戰額度、逐球狀態均與官方一致，才復原該事件；不能以官方總數單獨猜測球位。

| `game_pk` | feed → 官方 attempts | 復原位置（打席／球） | 官方分隊 residual | 結果 |
| --- | ---: | --- | --- | --- |
| 781155 | 1 → 2 | 14／4 | 主隊成功 1 次 | 嚴格復原 |
| 780622 | 4 → 5 | 55／4 | 客隊成功 1 次 | 嚴格復原 |
| 781032 | 4 → 5 | 29／4 | 主隊成功 1 次 | 嚴格復原 |
| 781697 | 6 → 7 | 65／3 | 客隊失敗 1 次 | 嚴格復原 |
| 780340 | 0 → 1 | 56／4 | 客隊成功 1 次 | 嚴格復原 |
| 780940 | 5 → 6 | 42／4 | 客隊成功 1 次 | 嚴格復原 |
| 752127、753397、753580 | 不符 | 2024 ABS-only CSV 無資料列 | 無法定位 | 整場排除 |
| 780468、780929 | 不符 | 2025 ABS-only 與 feed 同樣缺球 | 無法定位 | 整場排除 |

另重新取得五場未解比賽的官方 feed：四場位元組 SHA 未變；780468 的來源內容雖有改變，挑戰仍為 feed 2／2 對官方 3／3。故五場維持 `recovery_unresolved`，不推定不存在挑戰，也不從同年度其他比賽選補樣。兩場曾標記「無官方 counter」的 753330、780436，實際是明示 `hasChallenges:false` 且兩隊成功／失敗均為零；現在可獨立核對零次，與真正缺欄區分。

## 固定樣本與模型輸入

最新本機報告 `data/processed/dataset_b_population_preparation_2026-09-29-v12.json`：96 場 feed 取得；85 場原樣通過、6 場復原通過、5 場無法定位而排除。91 場納入比賽全部通過官方終場計數、完整逐球對齊與來源指紋檢查。候選檔在 `data/processed/dataset_b/candidates_v4/`，共 14,223 筆 called-pitch 候選：13,132 筆有額度且非明確位置球員投手的 `provisional_opportunity`、1,042 筆零額度、49 筆明確位置球員投手。未把後兩類當作模型風險集。

| 時間切分 | 納入場次 | 暫定風險集 | 下一次同隊風險集機會到達 | 九局內右設限 |
| --- | ---: | ---: | ---: | ---: |
| Train | 43 | 6,297 | 6,211 | 86 |
| Validation | 12 | 1,636 | 1,612 | 24 |
| Test | 12 | 1,828 | 1,804 | 24 |
| External | 24 | 3,371 | 3,323 | 48 |
| 合計 | 91 | 13,132 | 12,950 | 182 |

`arrival_target.pitch_gap` 現在量至**同隊下一個仍屬風險集的暫定候選**；零額度與位置球員投手候選不能終止間隔。無後續候選時量至第 1–9 局投球終點並明示右設限。這只是歷史行動路徑上的觀察性間隔，不是改判後的反事實路徑。模型輸入只允許投球前狀態、當時挑戰餘額、原判、決策隊及進攻／防守方；`actual_challenge`、S0／S1 估值、對齊證據及到達標籤均不可作 predictor。按 `game_pk` 切分，單場不得跨組；外部 2026 場次仍需與開發清冊隔離。

`config/dataset_b_model_input_policy.json` 預先鎖定固定選場指紋、五場排除、91 場及 split 配額、風險集、特徵與標籤白名單；`data/processed/dataset_b_limited_model_input_gate_2026-09-29-v4.json` 對選場指紋、各候選檔 SHA、來源及逐筆到達序列重驗，得到 `limited_observational_baseline_input_ready=true`。這僅允許下一步研究**公開來源可觀測暫定候選的觀察性到達基線**。模型訓練、Validation／Test／External 評估、校準尚未執行；不得稱已得到 Future Opportunity 模型。

## 不能升格的限制

- ABS technical outage／replay 後挑戰資格沒有逐球可驗證的完整來源；所有相關欄位維持 `unknown`，`formal_legal_opportunity_ready=false`。即使技術故障是特殊事件，亦不能把未知資格默認為全場合法。
- 五場排除可能有非隨機選樣偏差；須在後續敏感度分析報告 96 場固定分母與 5／96 排除，不能只報 91 場成績。
- 歷史挑戰改變後續額度與比賽狀態；觀察性到達模型不可直接代入挑戰／不挑戰的反事實樹。正式 Dynamic Policy、跨 ±5 分 continuation、RRA 仍未完成。
- 固定官方 WP 快照涵蓋至 2025；本案 2025 Test 對機會模型可作時間測試，但不能宣稱對官方 WP 完全獨立。
- 來源快取、候選檔及閘門 JSON 受 `.gitignore` 排除，不會自動出現在其他 clone。此次執行時 Git HEAD 為 `f9883721bcc9d62fcc999e6f36f5e8488e972b6c` 且工作目錄有未提交變更；這是開發重播證據，不可追溯宣稱為正式、乾淨 commit 實驗。

## 離線重播與檢查

在保有相同本機來源快取、官方 WP baseline、選場 JSON 的專案根目錄執行，輸出必須是新路徑：

```powershell
$env:PYTHONPATH = "src"
python scripts/prepare_dataset_b.py --selection data/processed/dataset_b_schedule_selection_2026-09-24-v3.json --output data/processed/dataset_b_population_preparation_replay.json --candidates-dir data/processed/dataset_b/candidates_v4 --offline --reconcile-abs
python -m abs_challenge.dataset_b_readiness --selection data/processed/dataset_b_schedule_selection_2026-09-24-v3.json --preparation data/processed/dataset_b_population_preparation_replay.json --policy config/dataset_b_model_input_policy.json --output data/processed/dataset_b_limited_model_input_gate_replay.json
python -m unittest discover -s tests -v
```

第一個指令因五場被保守排除會回傳 exit code 1；這是原準備程式的「未全數通過」訊號，**不是**其餘 91 場失敗。必須再檢查輸出狀態及第二個限定模型輸入閘門；不得忽略其他意外失敗。v11→v12 的 96 場狀態、候選數與 CSV／ABS 來源清冊一致；v12 更新的是正確的風險集到達標籤。v12→v13 離線重播的全部逐場資料及來源 manifest 完全一致，限定閘門統計亦一致。全套 255 項測試通過。
