# ABS Challenge 決策研究

本 context 定義 ABS Challenge 資料與決策模型的共同語言，避免把規則允許、研究判定、實際行為與翻判結果混為一談。

## 判決與事件

**Original Umpire Call**：
ABS review 前主審在場上的 ball／strike 判決。
_避免：_ 把 feed 內翻判後的 call 稱為原判

**ABS Call**：
ABS review 確認或修正後的最終 ball／strike 結果。
_避免：_ Original call、challenge result

**Challenge Attempt**：
符合資格的球員實際要求 ABS review 的事件。
_避免：_ Opportunity、candidate

**Successful Overturn**：
ABS Call 與 Original Umpire Call 不同、因此翻轉原判的 Challenge Attempt。
_避免：_ Successful challenge（未說明成功意義時）

## 機會分類

**Legal Challenge Opportunity**：
依當時規則、判決方向、球員資格與剩餘額度，決策方可以提出 Challenge 的 adverse called pitch。
_避免：_ Actual challenge、reasonable opportunity

**Reasonable Challenge Candidate**：
Legal Challenge Opportunity 中，依已版本化的研究準則被選為值得分析的候選球；它是分析標籤，不是實際行為或最佳 policy。
_避免：_ Legal opportunity、optimal challenge

**Adverse Called Pitch**：
對某決策方不利的主審判決；called strike 對打方不利，called ball 對守方不利。
_避免：_ Incorrect call（除非已有 ABS 結果）

## 資源與決策

**Decision Side**：
受到 adverse call 且可考慮 Challenge 的一方；called strike 對應 batting side，called ball 對應 fielding side。
_避免：_ Challenger role、特定球員

**Decision Team**：
擁有該次 Challenge Budget 並承擔使用或保留決策結果的球隊。
_避免：_ 發起 Challenge 的個別球員

**Challenger Role**：
實際發起 Challenge 的 batter、pitcher 或 catcher；只用於資料品質與次要行為分析，不定義核心 team-level policy。
_避免：_ Decision side、Decision team

**Challenge Budget**：
球隊在某一決策時點可承擔失敗 Challenge 的有限額度。
_避免：_ Attempt count、overturn count

**Challenges Remaining**：
某次 Challenge decision 發生前，指定球隊尚可使用的 Challenge Budget 狀態。
_避免：_ 終場剩餘額度

**Challenge Option Value**：
在相同 Game State 下，多保留一單位 Challenge Budget 對 Expected Win Probability 的邊際價值。
_避免：_ 單次翻判價值

**Required Recognition Accuracy**：
在指定 Game State 與 Challenges Remaining 下，現在提出 Challenge 優於保留額度所需的最低主觀 overturn probability。
_避免：_ Overturn prediction、球員真實 confidence

## 制度與資料範圍

**Challenge System**：
由合資格球員主動要求 ABS review、且受 Challenge Budget 限制的制度。
_避免：_ Full ABS

**Full ABS**：
每球由 ABS 自動決定 ball／strike、沒有 Challenge decision 的制度。
_避免：_ Challenge System

**Rule Regime**：
在特定 competition、season、日期與 league 範圍內適用的一組 ABS format 與 Challenge Budget 規則。
_避免：_ 只用年份推定規則

**Observed Format Confirmation**：
歷史官方 live feed 實際出現 `reviewDetails.reviewType = MJ`，因此只把該場確認為 Challenge System。人工傳入 `--abs-format challenge` 本身不是確認證據，也不得把單場證據外推為整季分類。
_避免：_ 使用者參數即官方證據、全年皆為 Challenge System

**Regulation-Inning Primary Scope**：
本次研究只估計第 1–9 局的 Challenge decision；第 10 局以後的額度與 policy 屬未來 Extension。
_避免：_ 把工程上的延長賽解析能力稱為本次研究成果

**Regulation Boundary Value**：
九局結束平手時使用的外生 Expected Win Probability，用來結束 regulation-inning 模型而不研究延長賽內的 Challenge policy。
_避免：_ Extra-inning policy、把九局平手視為比賽結束

**Phase 0 Game Pass**：
單場資料在事件、規則、ledger、Savant join、必要狀態、Decision Side 與挑戰資格上完整通過；若官方 `gameData.absChallenges` counter 可用，attempts 與 overturned 也必須完全一致。守方 pitcher／catcher 歸因缺失不阻擋。
_避免：_ Phase 0 Gate Pass

**Phase 0 Gate Pass**：
跨年度 cohort、所有單場 audit 與官方 aggregate comparison 都滿足版本化門檻。
_避免：_ 單場 audit pass

目前版本已於 2026-09-12 以 12 場 regulation-only 樣本通過 Phase 0 Gate；61 次 attempts／30 次 overturned 與官方 counter 完全一致。這只授權進入 Phase 1 RE／WP baseline，不代表 Legal Opportunity 排除條件、Future Opportunity、Dynamic Policy 或 RRA 已完成。
