# Dataset B 賽程候選清冊：2026-09-24

本次只鎖定公開賽程 metadata 中的候選 `game_pk`；尚未下載這些場次的完整逐球資料、確認逐場 ABS 規則或驗收正式 Legal Opportunity。不得將此清冊稱為已完成的 Train／Validation／Test／External holdout 或模型評估結果。

## 預宣告抽樣與結果

抽樣規則見 [`config/dataset_b_sampling.json`](../config/dataset_b_sampling.json)，時間窗及 39 場既有開發排除清冊見 [`config/dataset_b_split_plan.json`](../config/dataset_b_split_plan.json)。每窗只讀 MLB Stats API 的賽程日期、比賽類型、最終狀態、預定局數、球隊聯盟／層級及 `game_pk`；不依比分、ABS 次數或逐球結果選場。依固定 seed 與 `SHA-256(seed|window|game_pk)` 排序，短缺不依結果遞補。96 場是有界的工程預備樣本，非正式樣本量／效力設計。

| 時間窗 | 賽程合格候選 | 固定配額 | 選入 | 短缺 |
| --- | ---: | ---: | ---: | ---: |
| 2024 IL Train | 672 | 24 | 24 | 0 |
| 2025 IL 前段 Train | 673 | 24 | 24 | 0 |
| 2025 IL Validation | 463 | 12 | 12 | 0 |
| 2025 IL Test | 169 | 12 | 12 | 0 |
| 2026 MLB External | 2,287 | 24 | 24 | 0 |

合計 96 個唯一 `game_pk`，與 39 場已知開發樣本交集為 0；五份來源 manifest 已寫入本機清冊。官方賽程對改期比賽可能同時列出原排程日及正式日期；程式只採 `officialDate` 當日紀錄，本次忽略 153 筆非正式日期 listing，不將它們視為額外比賽。選入場次的日期、制度時間窗與聯盟／層級通過賽程 metadata 檢查。賽程的九局欄位是「預定」局數，不等於實際 regulation-only；仍須逐場核實。

本機清冊為 `data/processed/dataset_b_schedule_selection_2026-09-24-v3.json`，`selection_sha256` 為 `c8ac1bd600d216be617e54a86e539efe3091d14dea46ad6c58390c6b8104c20f`。五份來源快取位於 `data/raw/dataset_b/source_cache/`；資料檔受 `.gitignore` 排除，其他 clone 不會自動擁有。原網路權限失敗的 v1 與重複賽程檢查失敗的 v2 清冊也保留，不覆寫歷史。使用相同快取離線建立 v4，選場指紋與 v3 相同、下載數為 0。

重播指令（需先具備本機來源快取，輸出檔名必須尚不存在）：

```powershell
$env:PYTHONPATH = "src"
python -m abs_challenge.dataset_b_sampling --sampling-plan config/dataset_b_sampling.json --split-plan config/dataset_b_split_plan.json --cache-dir data/raw/dataset_b/source_cache --output data/processed/dataset_b_schedule_selection_replay.json --offline
```

## 尚未完成的閘門

- 對每個選入場次取官方 feed，確認實際為兩次制、完整 1–9 局資料、逐球對齊與來源資格；無證據者維持排除或 unknown，不以賽程欄位推定。
- ABS 技術停用與 replay 後不可挑戰的時序證據仍不足；`source_eligibility_status` 一律為 `provisional_source_limitations`。
- 在上述資格、樣本支持及決策時特徵稽核完成前，`holdout_game_lists_locked=false`、`formal_model_evaluation_ready=false`，不啟動 Future Opportunity 訓練或正式策略評估。
