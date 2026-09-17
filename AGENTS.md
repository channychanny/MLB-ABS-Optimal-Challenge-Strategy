# AGENTS.md

## 語言規範

- 無論使用者以何種語言提出要求，所有回覆與溝通一律使用繁體中文。
- 新建立或更新的文件、規格、Issue、註解及其他文字內容一律使用繁體中文。
- 程式語法、識別字、API 名稱、CLI 指令、資料欄位及業界固定術語可保留英文。

## 專案狀態

這是既有且仍在進行中的研究專案。保留已完成的工作，並以增量方式擴充；不得重新初始化專案、刪除既有成果或重寫已完成的功能。

專案已於 2026-09-12 通過 **Phase 0 — Data Feasibility Gate（資料可行性閘門）**：2023–2025 Triple-A 與 2026 MLB 各 3 場 regulation-only 樣本通過 audit，61 次 attempts／30 次 overturned 與官方終場計數完全一致。2026-09-15 使用者同意 Phase 1 以官方 ±5 分覆蓋作限定原型驗收；三場／16 次挑戰仍保留 4 次缺值，不能改稱全數估值成功。目前進入 Phase 2，自建資料與 RE 開發估計不等於已完成 WP 訓練、校準、正式 Dynamic Policy 或 RRA。

## 開始工作前必讀

進行實質變更前，先閱讀與任務相關的下列文件：

- `README.md`
- `MLB ABS Optimal Challenge Strategy — 產品規格書.md`
- `reports/phase0_feasibility.md`
- `docs/data_dictionary.md`
- `docs/evaluation_design.md`
- `config/rule_regimes.json`
- `config/phase0_gate.json`
- `CONTEXT.md`（若存在）
- `docs/adr/` 下與任務相關的 ADR（若存在）
- `.scratch/phase0-hardening/map.md`（處理 Phase 0 時）
- `docs/phase2_dataset.md`、`config/phase2_dataset.json`、`.scratch/phase2-models/map.md`（處理 Phase 2 時）

## 重要實作脈絡

- Challenge 翻判成功時，MLB live feed 儲存的是 ABS 修正後判決；原始裁判判決為其相反結果。
- 部分 Triple-A 終局打席的 Challenge 僅出現在 plate-appearance result description，沒有逐球 `reviewDetails`。
- Stats API 與 Savant 的串接鍵為 `game_pk`、Savant 的一基底打席編號（`at_bat_index + 1`）及 `pitch_number`。
- 上述三欄鍵不可無條件外推到所有歷史投球：敬遠保送與計時器違規的 `no_pitch` 自動判決可能增加 Statcast 列，甚至使後續實際投球編號偏移。Dataset A 現行先整場排除不符者；不得僅刪除 `automatic_ball/automatic_strike` 列後照原編號 join。修正追蹤於 Phase 2 Issue 06。
- 歷史資料可能缺少挑戰者身分。應保留缺失狀態，不得自行推定 pitcher 或 catcher。
- 核心研究的決策單位是 Decision Team；守方已知但 pitcher／catcher 無法細分時可進入 team-level Gate，精確角色只供次要行為分析。
- `config/rule_regimes.json` 中 2023／2024 年 6 月 25 日前仍需逐場 format 證據；官方 feed 實際出現 `reviewType=MJ` 時只確認該場，沒有事件證據時人工 `--abs-format` 不得把狀態升級為 confirmed。
- `phase0_game_pass` 只是單場結果；只有跨年度 `phase0_gate_pass` 才授權進入 Phase 1。
- 單場有 `gameData.absChallenges` 時，逐球 attempts／overturned 必須與官方終場 counter 完全一致；`official_counter_pass = false` 一律阻擋單場 Gate。
- `pitch_observation`、翻判結果與 `delta_*` 是 label／事後資料，不得加入 decision-time model features。
- 主要研究範圍只含第 1–9 局；延長賽解析屬工程防呆，延長賽 Challenge policy 是 MVP 後的 extension。
- 九局平手使用明確版本化的 Regulation Boundary Value，不得直接視為比賽結束。
- Legal Opportunity 的 ABS technical outage 與 post-replay-review 排除仍未完成，schema 必須維持 `provisional_source_limitations`，不得把 Phase 0 pass 說成完整研究資料已定稿。
- 正式模型實驗必須記錄實際執行版本的 commit SHA 與工作目錄狀態。使用者於 2026-09-16 授權建立 Git 版本紀錄並推送至 `channychanny/MLB-ABS-Optimal-Challenge-Strategy`；本機沿用遠端 `main` 歷史，不得重建或強制覆寫。既有未記錄 commit 的開發產物不得追溯宣稱為正式實驗；後續提交與推送仍依各次任務授權。
- 下載及產生的資料集受 `.gitignore` 排除；不得假設每個 clone 都有本機樣本資料。
- Dataset A 使用完整 MLB 一般投球，不限 ABS Attempts；Train 2019／2021–2023、Validation 2024、Test 2025、External 2026，同場不可跨 split。RE 與九局平手邊界只 fit Train。
- 自建模型保留真實分差，不截成 ±5；分差 0–5／6–10／11+ 分別報告樣本支持。缺乏資料不能宣稱已可靠覆蓋。
- RE 開發版只納入滿三出局的半局；再見半局仍有 WP 勝負標籤，但 RE 為 null。空 RE 格子不得填零。校準與正式 WP 評估尚未實作。

## 驗證

在專案根目錄執行標準函式庫測試：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Agent skills

### Issue tracker

Issue 與規格以本機 Markdown 檔案追蹤，存放於 `.scratch/`。詳見 `docs/agents/issue-tracker.md`。

### Domain docs

本專案採用 single-context 配置：根目錄使用 `CONTEXT.md`，ADR 存放於 `docs/adr/`。詳見 `docs/agents/domain.md`。
