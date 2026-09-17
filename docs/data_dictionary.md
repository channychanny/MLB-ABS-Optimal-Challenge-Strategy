# Phase 0 資料字典

## 資料來源

- MLB Stats API live feed：`https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live`
- Baseball Savant ABS Challenge CSV：2025／2026 可用於實際 Challenge 的事件 join；2023／2024 的 `hfABSFlag` 查詢可能回傳 0，歷史場次改用完整逐球 CSV join。
- Baseball Savant 完整逐球 CSV：供 Legal／Reasonable Opportunity population 建構。
- `config/rule_regimes.json`：依 competition、season、日期與 league 解析規則。
- `config/phase0_gate.json`：版本化跨年度驗收門檻。

官方定義與規則參考：

- [Baseball Savant ABS Metrics Documentation](https://baseballsavant.mlb.com/abs-metrics-documentation)
- [MLB 2026 ABS Challenge System 說明](https://www.mlb.com/athletics/news/abs-challenge-system-mlb-2026)
- [2024 Triple-A Challenge System 調整](https://www.mlb.com/milb/news/triple-a-abs-challenge-system)
- [2024 International League／Pacific Coast League 額度說明](https://www.mlb.com/news/abs-system-futures-game-strike-zone-box-broadcast)
- [2023 Triple-A 制度說明](https://www.mlb.com/news/abs-system-gets-rigorous-test-at-futures-game)

每次下載都應保存 companion manifest，至少包含 source URL、request parameters、UTC retrieval time、SHA-256、byte length 與 row count。

## Challenge Event 與 Ledger

| 欄位 | 定義 |
|---|---|
| `game_pk` | 官方比賽識別碼 |
| `at_bat_index` | live feed 的零基底打席序號 |
| `pitch_number` | 打席內逐球序號 |
| `play_event_index` | 包含非投球 action 的 feed event 序號 |
| `original_call` | ABS review 前的主審判決 |
| `abs_call` | feed 儲存的確認或修正後 ABS 結果 |
| `overturned` | ABS 是否翻轉原判 |
| `challenge_team_id` | 提出 Challenge 的球隊 |
| `challenge_team_source` | `feed` 或由判決與半局推得 |
| `expected_challenge_team_id` | 依 adverse call 與半局推導的合理挑戰方 |
| `challenge_team_matches_call` | feed／推定球隊是否符合判決方向 |
| `review_source` | pitch-level review 或 plate-appearance result fallback |
| `challenger_role` | `batter`、`pitcher`、`catcher`、`batter_inferred`、`fielder_unknown` 或 `unknown` |
| `balls_before`、`strikes_before` | Challenge 前 count |
| `balls_after_original`、`strikes_after_original` | 原判維持的 counterfactual count |
| `balls_after_abs`、`strikes_after_abs` | ABS 結果成立後 count |
| `challenges_before` | 該次嘗試前球隊剩餘額度 |
| `challenges_after` | 該次嘗試後球隊剩餘額度 |
| `valid_budget` | 嘗試前是否至少還有一次 Challenge |

`fielder_unknown` 表示已能由 adverse call 與半局確認 Decision Side 是守方，但來源不足以再區分 pitcher／catcher；可用於核心 team-level policy。`unknown` 表示記錄中的發起球員與規則資格無法一致解釋，會阻擋單場 Gate。

Audit v2 另提供：

- `challenger_eligibility_pass`：是否沒有無法解釋的 `unknown` 角色。
- `fielder_role_unresolved`：守方無法細分 pitcher／catcher 的事件數。
- `challenger_eligibility_failures`：真正無法確認規則資格的事件數。
- `exact_role_attribution_complete`：所有 Attempt 是否都有精確或可唯一推得的角色；此欄只作資料品質指標。
- `official_counter_available`／`official_counter_pass`：官方終場 ABS counter 是否存在，以及逐球 attempts／overturned 是否完全一致；存在但不一致會阻擋單場 Gate。

## Savant Join

唯一 join key 為：

```text
game_pk + (at_bat_index + 1) + pitch_number
```

Savant 的 `at_bat_number` 是一基底；Stats API 的 `atBatIndex` 是零基底。重複或無法解析的 join key 會直接拋錯，避免靜默覆寫。

### `statcast_pre_pitch_state`

此 namespace 僅存放判決前可用的狀態：

- `balls`、`strikes`、`outs_when_up`
- `inning`、`inning_topbot`
- `home_score`、`away_score`、`bat_score`、`fld_score`
- `on_1b`、`on_2b`、`on_3b`
- `home_win_exp`、`bat_win_exp`（只能作外部 baseline；正式自建 WP 模型不得把同場事後修訂值當成獨立真值）

Phase 0 必要欄位缺失會令單場稽核失敗；壘包無人以空值表示，屬合法 nullable 欄位。

### `statcast_pitch_observation`

此 namespace 是投球發生後的觀察／標籤資料：

- `description`、`des`
- `plate_x`、`plate_z`、`sz_top`、`sz_bot`
- `delta_home_win_exp`、`delta_run_exp`

這些欄位不得直接進入 decision-time model feature matrix。尤其 `delta_*` 不得代替 \(S_0\) 與 \(S_1\) 的 counterfactual 估值。

## Challenge Opportunity

| 欄位 | 定義 |
|---|---|
| `decision_team_id` | adverse called strike 時為打方；adverse called ball 時為守方 |
| `original_call` | `strike` 或 `ball` |
| `challenges_remaining` | 該球判決當下決策方剩餘額度 |
| `actual_challenge` | 是否實際提出 Challenge；僅為行為標籤 |
| `overturned` | 實際 Challenge 的結果；未挑戰為 `null` |
| `reasonable_candidate` | `true`、`false` 或資料不足時的 `null` |
| `reasonable_reasons` | 版本化 heuristic 命中的理由 |
| `pre_pitch_state` | 決策前特徵 namespace |
| `pitch_observation` | 事後觀察／標籤 namespace |

Legal Opportunity 目前定義為：called ball／called strike 對某隊不利、該隊仍有額度，且不是官方名冊可明確判定的 position player pitching 情境。球員 metadata 不足時不臆測排除。官方定義另外排除 ABS technical outage；MLB 規則亦不允許 replay review 後再提出 ABS Challenge，但目前來源尚未提供可靠、逐球一致的排除旗標。因此 `legal_opportunity_criteria.status` 為 `provisional_source_limitations`，這兩種排除未完成前不可宣稱 Legal population 已與官方完全一致。

主要 opportunity dataset 只保留 `inning` 1–9；延長賽事件可出現在 audit ledger，但不進入本次研究的 Opportunity、RRA 或 Policy population。

Reasonable Candidate v1 為研究用 heuristic，而非正式 policy：已知翻判成功、estimated challenge rate 達門檻，或球位接近好球帶邊緣且事後 run value 達門檻時標記為候選。因其使用事後資料，僅能作 label／篩選與敏感度分析。

## 已確認 feed 行為

- Challenge 失敗時，feed 判決不變。
- Challenge 成功時，feed 儲存修正後 ABS call；`original_call` 必須取相反值。
- sampled 2025 Triple-A feed 缺少 `reviewDetails.player`。
- sampled 2026 MLB feed 通常有 player，但 terminal fallback 仍可能缺少。
- 部分 terminal 2025 Triple-A Challenge 只存在 plate-appearance result description。
- 2023／2024 歷史 feed 中的 `reviewDetails.reviewType = MJ` 可作該場確實採用 Challenge System 的事件證據；只確認該場，不外推全年 format。
- 官方 live feed 的 `gameData.absChallenges.usedSuccessful/usedFailed` 可作逐球擷取 attempts／overturned 的獨立終場計數核對。

## 尚未確認的資料假設

- 目前只確認 Phase 0 抽樣場次的 Challenge System 標籤；尚未建立涵蓋 2023／2024 全季的逐場 Challenge System／Full ABS 清冊。
- 2024 Phase 0 樣本已同時驗證 International League 兩次額度與 Pacific Coast League 三次額度 regime；正式行為分析仍需擴大日期覆蓋。
- position player pitching 的辨識依賴 live feed 名冊；資料缺失時無法保證完整排除。
- ABS technical outage 與 post-replay-review 的 Legal Opportunity 排除尚未實作。
- Phase 0 已完成 regulation-only 樣本的官方 game-record comparison；尚未建立每年度全季 aggregate comparison。
