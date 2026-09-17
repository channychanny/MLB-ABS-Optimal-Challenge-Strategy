# MLB ABS Optimal Challenge Strategy
## 產品規格書 Product Requirements Document

**Project Name:** MLB ABS Optimal Challenge Strategy  
**中文名稱：** MLB ABS 最佳挑戰時機與資源配置分析系統  
**版本：** v1.4  
**專案類型：** Data Science / Baseball Analytics / Decision Optimization  
**主要技術：** Python、MLB Statcast、Minor League Statcast、MLB Stats API、Machine Learning、Dynamic Programming、Monte Carlo Simulation、Streamlit

**v1.4 範圍決策：** 主要研究、Opportunity dataset、RRA 與 Policy Evaluation 僅涵蓋第 1–9 局；延長賽 Challenge policy 留待 regulation-inning MVP 完成後擴充。核心決策單位為 Decision Team，精確 pitcher／catcher 發起角色只供次要行為分析。

---

# 1. 專案背景

MLB 自 2026 年正式導入 Automated Ball-Strike Challenge System（ABS Challenge System）。

本專案以 **2026 MLB 正式規則**作為唯一主要策略制度：

- 每隊開賽擁有 **2 次 Challenge**
- Challenge 成功後保留挑戰額度
- Challenge 失敗才會消耗 1 次
- 只有打者、投手及捕手可以提出 Challenge
- 必須於主審判決後立即提出

因此本研究的 Challenge Budget 僅考慮：

\[
c\in\{0,1,2\}
\]

專案不建立 3 次 Challenge 制度的正式策略模型。

Minor League 過去曾測試 3 次 Challenge 制，該資料可作為歷史行為或敏感度分析使用，但不會影響本研究最終針對 MLB 2026 規則產生的策略結果。

---

# 2. 核心研究問題

本專案不研究：

> 「這一球 Challenge 是否會成功？」

原因是當精確 ABS pitch location 與 strike-zone 規則已知時，Challenge 結果接近 deterministic。

本專案真正研究：

> **在 MLB 每隊只有 2 次 Challenge 的制度下，目前使用一次 Challenge，與將它保留給未來相比，哪一個選擇能帶來較高的 Expected Win Probability？**

進一步希望回答：

> **在特定比賽情境下，球員至少需要多高的判斷可靠度，現在使用 Challenge 才合理？**

---

# 3. Primary Objective

建立一套適用於 **MLB 2026 兩次 Challenge 制**的 Data-Driven ABS Challenge Decision Framework。

模型必須能計算：

1. 主審判決翻轉所帶來的 Win Probability Value。
2. 尚未使用 Challenge 的未來 Option Value。
3. 剩餘 2 次與剩餘 1 次 Challenge 時策略有何差異。
4. 每個 Game State 所需的最低 Required Recognition Accuracy。
5. Batter / Pitcher / On-deck hitter 等球員情境是否改變最佳 Challenge Threshold。

---

# 4. 主要研究問題

## RQ1 — Game-State Challenge Value

不同 Game State 下，一次成功翻判能帶來多少 Win Probability 改變？

主要狀態包括：

- Inning
- Top / Bottom
- Score Differential
- Outs
- Base State
- Ball-Strike Count

定義：

\[
\Delta WP =
WP(S_{overturned})-
WP(S_{call\ stands})
\]

---

## RQ2 — Challenge Option Value

在兩次 Challenge 制度下：

> 現在多保留一次 Challenge，到底值多少？

定義：

\[
COV(S,c)=V(S,c)-V(S,c-1)
\]

其中：

\[
c\in\{1,2\}
\]

\(V(S,c)\) 代表目前位於狀態 \(S\)，剩下 \(c\) 次 Challenge，且後續皆採最佳策略時的 Expected Win Probability。

因此主要研究：

\[
V(S,2)-V(S,1)
\]

與：

\[
V(S,1)-V(S,0)
\]

兩種 Challenge scarcity。

---

## RQ3 — Required Recognition Accuracy

計算每個 Game State 的最低 Challenge 判斷可靠度：

\[
RRA(S,c)=p^*
\]

例如：

\[
RRA(S,1)=0.65
\]

代表：

> 當球隊只剩最後一次 Challenge 時，在此 Game State 中，只有當球員認為自己的判斷可靠程度至少約為 65%，現在使用 Challenge 才具有正的策略價值。

此門檻代表：球員根據當下可取得資訊，至少需相信此球有 65% 的機率會被翻判，Challenge 才值得使用。

RRA 是一個 **決策門檻**，不是事後的翻判結果，也不是假設球員能直接看到精確 ABS 座標。

---

## RQ4 — Remaining Challenge Effect

直接比較：

\[
RRA(S,2)
\]

與：

\[
RRA(S,1)
\]

研究：

> 同一個 Game State，如果球隊還有 2 次 Challenge，是否應該比只剩 1 次時更加積極？

預期：

\[
RRA(S,1) > RRA(S,2)
\]

但實際差異須由 Dynamic Model 決定。

---

## RQ5 — Player-Aware Strategy

比較：

### League-Average Model

\[
WP=f(GameState)
\]

與：

### Player-Aware Model

\[
WP=
f(
GameState,
BatterStrength,
PitcherStrength,
OnDeckStrength,
Platoon
)
\]

回答：

> 同樣 Game State，如果目前是中心打者或後段打者，最佳 Challenge Threshold 是否不同？

此處的 `PitcherStrength` 指當前投手對 Game State 與 WP 的影響，不是「這次 Challenge 由 pitcher 或 catcher 發起」。核心模型以 Decision Team 為決策單位。

---

## RQ6 — Strategy Comparison

比較以下 Policy：

- Always Challenge
- Late-Inning Only
- High-Leverage Only
- Fixed Recognition Threshold
- Savant-style Static Strategy
- Dynamic Optimal Policy

所有策略均在 **2 次 Challenge 制**下評估。

---

# 5. 研究範圍

## In Scope

### MLB 正式規則

主要結果一律使用：

\[
InitialChallenges=2
\]

### Regulation Innings

本次研究的主要分析範圍固定為：

\[
Inning=1\sim9
\]

主要 Opportunity dataset、Policy Evaluation、RRA Table 與研究結論均排除第 10 局以後的決策。延長賽的 Challenge 補充規則、Opportunity arrival 與最佳使用策略不屬於本次研究問題，待 regulation-inning MVP 完成後再作 Extension。

九局結束平手時，不得把比賽當成勝負已定。MVP 使用一個明確揭露且固定的 **Regulation Boundary Value**，由 Savant baseline 或歷史平手進入延長賽後的最終勝率估計。此值只負責把九局平手狀態映射成 Expected Win Probability，不模擬延長賽內的 Challenge decision、額度補充或動態 policy。

### Challenge Remaining

模型只有三種狀態：

\[
c=0,1,2
\]

---

## Out of Scope

第一版不研究：

- 3 次 Challenge 制的最佳 Policy
- Full ABS games
- 第 10 局以後的 Challenge Opportunity、額度配置與最佳 Policy
- 延長賽 runner rule 與 Challenge refill 的動態模型
- ABS overturn prediction
- Computer Vision
- 即時場上操作工具
- 球員主觀 Confidence estimation
- Mobile App
- React / Next.js Frontend

---

# 6. 資料來源

本專案資料分為兩大類：

---

## Dataset A — MLB Historical Game Data

主要來源：

### MLB Statcast / Baseball Savant

建議年份：

\[
2019,\ 2021-2025
\]

2020 縮短球季不納入主要 WP / RE 訓練資料，可另作敏感度分析。

此年份範圍只適用於 MLB Historical Game Data；ABS Challenge Dataset 仍固定使用 2023–2025 Triple-A 與 2026 MLB，不涉及 2020 ABS 資料。

用途：

- Win Probability Model
- Run Expectancy
- Game-State Transition
- Player Strength
- General Baseball Event Distribution

主要欄位：

- game_pk
- inning
- inning_topbot
- balls
- strikes
- outs_when_up
- on_1b
- on_2b
- on_3b
- home_score
- away_score
- batter
- pitcher
- events
- description
- handedness

---

# 7. Dataset B — Historical ABS Challenge Data

ABS-specific 歷史資料主要使用：

## 2023 Triple-A

只保留：

> Challenge System games

排除：

> Full ABS games

---

## 2024 Triple-A

重點使用：

> Challenge System games

尤其 2024 年 6 月下旬後全面使用 Challenge System 的 Triple-A 資料。

---

## 2025 Triple-A

整季 Challenge System 資料。

此資料將是歷史 Challenge Behavior 與 Challenge Opportunity Distribution 的核心來源之一。

---

## 2026 MLB

正式：

> 2-Challenge MLB ABS System

主要用於：

- Final Validation
- MLB External Validation
- Actual MLB Behavior Comparison
- Final Policy Evaluation

---

# 8. Minor League 3-Challenge Data 的定位

過去 Minor League 曾出現：

\[
InitialChallenges=3
\]

此資料：

### 可以使用於

- Challenge usage descriptive analysis
- Resource scarcity sensitivity analysis
- 驗證「Challenge 越多是否使用越積極」
- Future methodological extension

### 不用於

- 主要 RRA Table
- 最終 Streamlit 推薦
- MLB Optimal Policy
- 核心 Dynamic Value Function

因此最終產品不提供：

```text
Initial Challenges:
2 / 3
```

選項。

系統固定為：

```text
MLB Rules
Initial Challenges = 2
```

---

# 9. Data Filtering Rules

Minor League ABS 資料進入核心 Challenge Opportunity Model 前，需符合：

### 必須是

```text
ABS_format = Challenge System
```

### 排除

```text
Full ABS
```

以及任何無 Challenge Decision 的比賽。

---

## 9.1 ABS Event Taxonomy

為避免將「可以挑戰」、「值得挑戰」與「實際挑戰」混為一談，資料需區分：

### Legal Challenge Opportunity

規則上允許提出 Challenge 的 adverse called pitch，例如打者面對 called strike，或守方 pitcher / catcher 面對 called ball，且該隊仍有 Challenge。

### Reasonable Challenge Candidate

在 Legal Challenge Opportunity 中，依 pitch location、potential value 或 empirical challenge probability 篩選出的合理候選球。

### Challenge Attempt

球員實際提出 Challenge 的事件。

### Successful Overturn

Challenge Attempt 後，主審原判被 ABS 翻轉的事件。

Future Opportunity Model 主要估計 Legal / Reasonable Opportunity 的到達過程；實際 Challenge Attempt 另用於 Historical Behavior Model，避免既有球員策略造成 selection bias。

---

# 10. 核心資料結構

一筆資料基本單位：

> Pitch × Game State

主要 Game-State Features：

\[
X=
\{
inning,
half,
scoreDiff,
outs,
baseState,
balls,
strikes,
homeAway
\}
\]

Challenge State：

\[
c\in\{0,1,2\}
\]

Player Context：

\[
X_{player}=
\{
BatterStrength,
PitcherStrength,
OnDeckStrength,
Platoon
\}
\]

---

# 11. Feature Engineering

## Game State

建立：

- score_diff
- base_state
- count_state
- remaining_outs
- home_away
- inning_phase
- leverage-related variables

---

## Batter Strength

候選：

- rolling wOBA
- rolling xwOBA
- BB%
- K%
- handedness

---

## Pitcher Strength

候選：

- rolling xwOBA allowed
- K%
- BB%
- pitcher handedness

---

## On-Deck Strength

使用：

- rolling offensive metric
- prior-to-game estimate

---

## Leakage Prevention

所有 Player Metrics 只能使用：

> 該場比賽開始前已存在的資料。

---

# 12. Model 1 — Run Expectancy Baseline

本專案不將既有 Run Expectancy 方法視為主要創新。採用：

1. MLB Baseball Savant 公開 RE24 / RE288 作為 Official External Baseline。
2. 使用本研究 Dataset A 獨立重算 RE24 / RE288，確保年份範圍、資料清理與結果可重現。

官方 baseline 參考：

- Baseball Savant Game Strategy Explorer
- Baseball Savant ABS Metrics Documentation

所有外部表格或欄位需記錄來源 URL、下載日期、適用球季與欄位定義。

自行重算：

## RE24

\[
8\times3
\]

以及：

## RE288

\[
8\times3\times12
\]

用途：

- Baseball Analytics Baseline
- Challenge Value sanity check
- 與官方 Savant 數值交叉驗證
- Savant-style Static Policy benchmark

自行重算結果若與官方 Savant 不一致，需檢查並記錄：

- 使用年份不同
- Regular Season / Postseason 範圍
- Extra-inning runner 規則
- plate appearance 與 inning terminal handling
- 資料清理與缺失值規則

但最終主要 decision metric 使用：

\[
WinProbability
\]

而不是 Run Expectancy。

---

# 13. Model 2 — Win Probability Model

本專案採取兩層 WP 架構：

## External WP Baseline

前期直接使用 Baseball Savant 公開的：

- `home_win_exp`
- `bat_win_exp`
- Game Strategy Explorer Win Probability table

用途：

- 快速跑通 Counterfactual / Dynamic pipeline prototype
- 作為 league-average WP benchmark
- 驗證自行訓練模型是否出現明顯偏差

Savant WP 不作為最終唯一依據，因其完整模型規格、版本更新與全部內部處理不由本專案控制，且不包含 batter / pitcher 等 Player Context。

---

## Reproducible Research WP Model

正式研究結果使用本專案自行訓練、可重現且可校準的 WP Model。

Target：

\[
Y=
\begin{cases}
1 & Team\ eventually\ wins\\
0 & Team\ eventually\ loses
\end{cases}
\]

---

## Baseline

Logistic Regression

---

## Statistical Model

GAM

---

## Machine Learning Model

XGBoost

XGBoost 只有在 out-of-sample calibration 或 scoring rule 明確優於較簡單模型時才作為主要模型；否則優先使用較容易解釋與重現的 Logistic Regression / GAM。

---

## Model A

\[
WP=f(GameState)
\]

---

## Model B

\[
WP=
f(GameState,PlayerContext)
\]

---

# 14. Win Probability Evaluation

主要指標：

- Brier Score
- Log Loss
- Calibration Curve
- 與 Savant WP 的 state-level comparison

不以 Accuracy 作主要評估指標。

---

## Temporal Validation

建議：

```text
Train:
2019、2021–2023

Validation:
2024

Test:
2025
```

2026 MLB 作：

> External / Prospective Validation

自行訓練模型與 Savant WP 的差異需按 inning、leverage、score differential、base-out state 與 count 分組檢查，而非只比較整體平均。

---

# 15. Model 3 — Counterfactual Challenge Value

每個 Challenge Situation 建立兩種 state：

## Original Call Stands

\[
S_0
\]

## Call Overturned

\[
S_1
\]

計算：

\[
\Delta WP=
WP(S_1)-WP(S_0)
\]

## Valuation Source Strategy

### Prototype

使用 Savant WP table 分別查詢 \(S_0\) 與 \(S_1\)，快速驗證 state reconstruction 與完整流程。

### Final Research Result

使用自行訓練且通過 calibration 的 WP Model 計算 \(S_0\) 與 \(S_1\)，並以 Savant WP 結果作 robustness comparison。

不得只把實際逐球資料中的單一 `home_win_exp` 或既有 delta 欄位直接視為 Challenge counterfactual，因為每個 Challenge Situation 需要分別估值實際未發生的另一個 state。

---

# 16. Model 4 — Future Challenge Opportunity Model

使用真實：

- 2023 AAA Challenge System
- 2024 AAA Challenge System
- 2025 AAA Challenge System
- 2026 MLB ABS

研究未來 Legal / Reasonable Challenge Opportunity 如何分布。

主要希望估計：

\[
P(
FutureChallengeOpportunity
|
GameState
)
\]

或：

\[
T=
TimeToNextChallengeOpportunity
\]

這個模型用於估計：

> 現在保留 Challenge 的未來價值。

不得只使用「實際提出 Challenge」的時間作為 opportunity arrival，因為實際行為同時受到球員判斷、既有策略與剩餘 Challenge 數量影響。Challenge Attempt 應另建 behavior model，或僅用於 empirical policy comparison。

---

# 17. Model 5 — Dynamic Challenge Value

核心決策情境：

\[
S=
(
GameState,
PlayerContext,
DecisionSide
)
\]

完整 Dynamic State：

\[
\tilde S=(S,c_{self},c_{opponent})
\]

其中：

\[
c_{self},c_{opponent}\in\{0,1,2\}
\]

完整 value function 寫為：

\[
V(S,c_{self},c_{opponent})
\]

若 MVP 不顯式加入 \(c_{opponent}\)，必須固定對手 policy，並將對手剩餘 Challenge 的影響 marginalize。此時可簡寫為 \(V(S,c_{self})\)，最終結論需明確標示此前提。

在此 MVP 簡化前提下建立：

\[
V(S,0)
\]

\[
V(S,1)
\]

\[
V(S,2)
\]

---

# 18. Dynamic Programming

在每個 Challenge Opportunity 比較：

\[
Q(S,Challenge)
\]

vs

\[
Q(S,NoChallenge)
\]

如果 Challenge 成功：

\[
c_{next}=c
\]

如果 Challenge 失敗：

\[
c_{next}=c-1
\]

因此：

### 若目前有 2 次：

\[
2
\rightarrow
2\quad(success)
\]

或：

\[
2
\rightarrow
1\quad(failure)
\]

### 若目前有 1 次：

\[
1
\rightarrow
1\quad(success)
\]

或：

\[
1
\rightarrow
0\quad(failure)
\]

---

# 19. Monte Carlo Simulation

針對指定 Game State：

模擬：

\[
10,000-100,000
\]

次剩餘比賽。

比較：

### Scenario A
Use Challenge Now

### Scenario B
Preserve Challenge

得到：

\[
P(Win|Challenge)
\]

與：

\[
P(Win|Save)
\]

Monte Carlo 同時作為：

- Dynamic Programming validation
- Sensitivity analysis
- Complex player-context simulation

---

# 20. Required Recognition Accuracy

最終解出：

\[
p^*(S,c)
\]

定義：

\[
p=P(Overturn\mid PlayerInformation,PitchContext)
\]

在原判維持後狀態為 \(S_0\)、翻判後狀態為 \(S_1\) 時：

\[
Q_{Challenge}
=
pV(S_1,c)+(1-p)V(S_0,c-1)
\]

\[
Q_{NoChallenge}=V(S_0,c)
\]

因此在分母為正且翻判對挑戰方有利時：

\[
p^*(S,c)=
\frac{V(S_0,c)-V(S_0,c-1)}
{V(S_1,c)-V(S_0,c-1)}
\]

RRA 即球員提出 Challenge 前所需的最低主觀 overturn probability。實作時必須另外說明 PlayerInformation 如何被估計或校準；若無法取得球員主觀訊號，則以固定 accuracy scenario 進行敏感度分析，不宣稱是在預測個別球員當下的真實 confidence。

主要產品只輸出：

\[
RRA(S,2)
\]

以及：

\[
RRA(S,1)
\]

不產生 3 次 Challenge 對應的 RRA。

---

# 21. 主要結果形式

例如：

| Situation | 2 Challenges Left | 1 Challenge Left |
|---|---:|---:|
| Early / Low Leverage | 80% | 89% |
| Midgame / RISP | 61% | 69% |
| Late / Close Game | 37% | 42% |
| 9th / High Leverage | 18% | 20% |

實際數值由模型產生。

核心研究：

> **Challenge scarcity 如何改變 optimal threshold？**

---

# 22. Player-Aware Analysis

比較同一 Game State：

### Elite Batter

\[
RRA_{elite}
\]

### Average Batter

\[
RRA_{avg}
\]

### Weak Batter

\[
RRA_{weak}
\]

並分別研究：

- current batter effect
- pitcher effect
- on-deck effect
- platoon effect

---

# 23. Historical Behavior Analysis

利用 AAA 與 MLB ABS 資料研究：

> 真實球員 Challenge timing 是否接近模型的 Optimal Strategy？

但此部分屬於：

**Empirical Validation / Secondary Analysis**

而不是核心模型本身。

若資料具備精確 `challenger_role`，可額外比較 batter／pitcher／catcher 的 Challenge rate 與 overturn rate；無法區分 pitcher／catcher 的事件仍可用於 team-level behavior，但不得進入角色間比較。

---

# 24. Policy Evaluation

所有 Policy 固定：

\[
InitialChallenges=2
\]

比較：

### Always Challenge

### Late-Inning Only

### High-Leverage Only

### Fixed Threshold

### Savant-style Static Policy

以官方 RE288 run value 與公開 confidence-level 方法建立靜態 benchmark：

\[
p^*_{SavantStatic}
=
\frac{0.2}{0.2+RunValue}
\]

此 Policy 只作比較基準，不等同本研究考慮未來 Challenge Option Value 的 Dynamic Optimal Policy。

### Dynamic Optimal Policy

---

# 25. Policy Evaluation Metrics

比較：

- Expected Win Probability
- Challenges Used
- Challenges Lost
- High-Value Opportunities Missed
- Low-Value Challenges Used
- Policy Regret

定義：

\[
Regret(\pi)
=
V(\pi^*)-V(\pi)
\]

---

# 26. Research Visualization

至少包含：

## RRA Heatmap

展示：

\[
RRA(S,2)
\]

與：

\[
RRA(S,1)
\]

分開畫圖。

---

## Remaining Challenge Effect

畫：

\[
RRA(S,1)-RRA(S,2)
\]

觀察：

> 只剩最後一次 Challenge 時，哪些 Game State 最需要變保守？

---

## Challenge Option Value

比較：

\[
V(S,2)-V(S,1)
\]

以及：

\[
V(S,1)-V(S,0)
\]

---

## Player Effect

展示：

\[
BatterStrength
\rightarrow RRA
\]

---

## WP Calibration

展示模型 probability quality。

---

## Policy Comparison

比較不同策略。

---

# 27. Streamlit Demo

Streamlit 為分析展示工具，不是即時球場操作產品。

---

## Input

### Game State

- Inning
- Top / Bottom
- Score Differential
- Outs
- Base State
- Ball Count
- Strike Count
- Called Ball / Called Strike

### Challenges Remaining

只允許：

```text
1
2
```

不提供：

```text
3
```

---

## Advanced

Optional：

- Batter Strength
- Pitcher Strength
- On-Deck Batter Strength
- Platoon

---

# 28. Streamlit Output

輸出：

### Win Probability — Call Stands

### Win Probability — Overturned

### Δ Win Probability

### Challenge Option Value

### Required Recognition Accuracy

### Difference Between 2 vs 1 Remaining Challenge

例如：

```text
Required Recognition Accuracy

2 challenges remaining:
52%

1 challenge remaining:
61%

Impact of having only one challenge:
+9 percentage points required
```

---

# 29. Data Architecture

```text
             MLB Historical Data
                      │
                      ▼
            Win Probability Model
                      │
                      ▼
              State Valuation
                      │
                      │
AAA 2023–2025 ABS ───┤
MLB 2026 ABS ────────┤
                      ▼
      Future Challenge Opportunity
                      │
                      ▼
             Dynamic Value Model
                      │
                ┌─────┴─────┐
                ▼           ▼
              V(S,2)      V(S,1)
                │           │
                └─────┬─────┘
                      ▼
                     RRA
                      │
              ┌───────┴───────┐
              ▼               ▼
       Research Analysis   Streamlit
```

---

# 30. MVP

## Phase 0 — Data Feasibility Gate

正式建模前必須先完成資料可行性驗收。需證明可以在逐球層級取得或可靠重建：

1. Challenge System / Full ABS 格式
2. Legal Challenge Opportunity
3. Challenge Attempt
4. Decision side（進攻方／防守方）與 decision team
5. Confirmed / Overturned result
6. Pitch sequence 與判決前後 count
7. 當時雙方 Challenges Remaining
8. Game State、比分、跑者與出局數

`challenger_role` 的精確 batter／pitcher／catcher 歸因屬資料品質與 Historical Behavior secondary analysis。核心 team-level Gate 必須能確認 decision side、decision team 與規則資格，但守方已知為 fielding side、僅無法再區分 pitcher／catcher 時，不阻擋 Phase 0。這類資料不得用於 pitcher-versus-catcher 行為比較。

驗收方式：從 2023–2025 Triple-A 與 2026 MLB 各抽樣比賽，逐球重建兩隊 Challenge ledger，並與官方 game record 或 ABS 統計核對。若剩餘 Challenge 無法直接取得，必須證明可由完整事件序列無歧義地重建。Phase 0 不強制納入延長賽樣本；現有延長賽 parser／ledger 測試只作資料工程 regression protection，不構成本次研究範圍。

若官方 live feed 提供 `gameData.absChallenges.usedSuccessful/usedFailed`，單場逐球擷取的 attempts 與 overturned 必須與終場 counter 完全一致；任何不一致均視為資料不完整，不得納入通過樣本。

只有通過此 Gate，才進入 WP、Future Opportunity 與 Dynamic Model。

---

## MVP Build Order

### Phase 1 — Official Baseline Prototype

1. 建立 Savant RE288 與 WP baseline snapshot
2. 以少量已驗證比賽重建 \(S_0\) / \(S_1\)
3. 使用 Savant WP 計算第一版 \(\Delta WP\)
4. 固定並記錄九局平手的 Regulation Boundary Value
5. 跑通不含 Player Context、只涵蓋第 1–9 局的簡化 Dynamic pipeline

此階段目標是驗證資料與決策流程，不宣稱已完成最終研究模型。

2026-09-15 使用者同意以官方 WP 表格主隊分差 −5 至 +5 作限定原型驗收。原三場／16 次挑戰中的 4 次大比分缺值保留，不改稱全數成功。此限制不縮減後續研究範圍。

### Phase 2 — Reproducible Research Models

1. 使用 Dataset A 自行重算 RE24 / RE288
2. 建立並校準 league-average WP Model A
3. 將自行訓練 WP 替換進 Counterfactual / Dynamic pipeline
4. 以歷史最終結果重估 Regulation Boundary Value
5. 與 Savant baseline 比較並記錄差異

自建資料與模型保留真實分差，不截成 ±5；依分差絕對值 0–5、6–10、11 分以上分組報告樣本量與預測表現。資料稀少或超出訓練支持範圍時需標記不確定性，不能把「模型可以輸出數值」當作「估值已可靠」。工作拆分見 [Phase 2 工作地圖](.scratch/phase2-models/map.md)。

### Phase 3 — Final MVP Evaluation

1. 建立 Future Opportunity Model
2. 估計 \(V(S,0)\)、\(V(S,1)\)、\(V(S,2)\)
3. 求解 RRA
4. 比較 Dynamic Policy 與 Savant-style Static Policy
5. 完成 robustness、sensitivity 與研究視覺化

---

最低完成條件：

1. MLB Historical Dataset
2. AAA ABS Challenge Dataset
3. Savant RE288 / WP External Baseline Snapshot
4. Independently Reproduced RE288
5. Calibrated League-Average WP Model A
6. Counterfactual Challenge Value
7. Future Challenge Opportunity Model
8. \(V(S,0)\)、\(V(S,1)\)、\(V(S,2)\)
9. Required Recognition Accuracy
10. 2 vs 1 remaining challenge comparison
11. Savant-style Static vs Dynamic Policy Comparison
12. Research Visualizations

Streamlit 不屬於研究成功的必要條件。

---

# 31. Full Version

MVP 後加入：

1. Player-Aware WP
2. Pitcher / Batter / On-deck effects
3. Monte Carlo simulation
4. Policy comparison
5. 2026 MLB external validation
6. Streamlit Dashboard
7. 延長賽 Challenge refill、Opportunity arrival 與 Dynamic Policy Extension

---

# 32. Risk Management

## Risk 1 — Historical ABS Data Availability

### 修正後評估

資料風險已因 2023–2025 Triple-A Statcast 與 2026 MLB ABS 而降低，但仍列為第一個 feasibility gate。

需確認的不是只有資料量，還包括：

- 是否可下載逐球 Challenge 欄位，而非只有 aggregate leaderboard
- 是否能辨識 Challenge System 與 Full ABS
- 是否能取得 confirmed / overturned 與 challenger role
- 是否能依完整序列重建雙方 Challenges Remaining
- 不同年度欄位與規則是否一致

若只能取得 aggregate data，Historical Behavior Analysis 仍可進行，但核心 sequential Dynamic Model 的可信度會明顯下降。

---

## Risk 2 — Different Historical Challenge Budgets

部分 Minor League 歷史資料使用 3 次 Challenge。

### Solution

主模型固定：

\[
InitialChallenges=2
\]

3 次 Challenge 資料：

- 不加入核心 Policy Output
- 不產生正式 RRA
- 僅用於行為與 scarcity sensitivity analysis

---

## Risk 3 — Full ABS vs Challenge System

部分早期 Triple-A 比賽採 Full ABS。

### Solution

只保留：

\[
ABSFormat=Challenge
\]

的比賽。

---

## Risk 4 — MiLB → MLB External Validity

AAA 球員、投手與 MLB 的競技環境不同。

### Solution

AAA ABS 資料主要用來估：

- Challenge Opportunity Distribution
- Historical Decision Behavior
- Resource Dynamics

最終策略再使用：

> 2026 MLB ABS

進行 external validation。

---

## Risk 5 — Future Challenge Option Value

核心困難仍是：

\[
V(S,c)-V(S,c-1)
\]

需要估計：

> 現在保留 Challenge 對未來的價值。

### Solution

結合：

- empirical ABS opportunity distribution
- Dynamic Programming
- Monte Carlo Simulation
- sensitivity analysis

---

## Risk 6 — State Space Explosion

加入：

- Game State
- Player Context
- Remaining Challenges

後狀態數量很大。

### Solution

使用：

- function approximation
- state aggregation
- simulation

---

## Risk 7 — External Baseline Dependency

Savant 的 WP / RE 欄位與頁面可作外部基準，但可能出現：

- 方法未完整公開
- 網頁或下載介面變動
- 歷史表格隨新增球季更新
- Statcast 欄位定義或資料修訂
- 無法支援 Player-Aware counterfactual

### Solution

- 保存帶有下載日期與參數的 baseline snapshot
- 保存欄位定義與來源 URL
- 不以外部 baseline 作唯一最終模型
- 正式研究結果使用可重現的自建 RE / WP
- 外部數值只用於 prototype、sanity check 與 robustness comparison

---

# 33. 專案主要 Data Science 結構

本專案核心流程：

**Historical Data**

↓

**Official Savant RE / WP Baseline**

↓

**Feature Engineering**

↓

**Win Probability Modeling**

↓

**Future Opportunity Modeling**

↓

**Counterfactual Valuation**

↓

**Dynamic Programming**

↓

**Monte Carlo Simulation**

↓

**Optimal Challenge Threshold**

因此專案核心為：

\[
\boxed{
Data
\rightarrow
Prediction
\rightarrow
Valuation
\rightarrow
Optimization
}
\]

---

# 34. 最終交付物

### Deliverable 1
Research Report

### Deliverable 2
GitHub Repository

### Deliverable 3
Research Presentation

### Deliverable 4
Streamlit Interactive Simulator

### Deliverable 5
README / Documentation

---

# 35. 最終專案核心

本專案的主要制度固定為：

\[
\boxed{
2\ Challenges
}
\]

並建立：

\[
\boxed{
GameState
+
PlayerContext
+
ChallengesRemaining
\rightarrow
OptimalChallengeThreshold
}
\]

其中：

\[
ChallengesRemaining\in\{1,2\}
\]

最終回答：

> **在 MLB 正式兩次 Challenge 制下，現在使用有限的 ABS Challenge，還是保留給未來，何者能最大化球隊 Expected Win Probability？**
