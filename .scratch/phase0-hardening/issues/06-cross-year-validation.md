# 06 — 完成跨年度資料驗收

Type: research  
Status: resolved

## 範圍

- 2023、2024、2025 Triple-A 與 2026 MLB 各至少 3 場通過 audit。
- 逐場確認 2023／2024 Challenge System／Full ABS。
- 確認歷史 regulation-inning 初始額度、成功保留規則與逐場 ABS format。
- 建立同 scope 的官方 attempts／overturn rate 對照。
- 量化 player-role 與 position-player-pitching metadata 缺失；角色缺失不阻擋 team-level Gate，但限制 role-specific analysis。
- 盤點 ABS technical outage 與 post-replay-review 的 Legal Opportunity 排除缺口；後續實作移至 Issue 07。

## 驗收條件

`validate-phase0` 依 `config/phase0_gate.json` 回傳 `phase0_gate_pass = true`，且報告記錄抽樣範圍與 manifest。

## Comments

2026-09-12：開始執行跨年度資料蒐集、逐場 format 證據與官方 aggregate 核對。

2026-09-12：12 場 regulation-only 跨年度樣本全數通過；2023、2024、2025 Triple-A 與 2026 MLB 各 3 場。2023 樣本由官方 feed 的 `reviewType=MJ` 確認逐場 Challenge System，Savant 完整逐球 CSV join 全數成功；2023／2024 均涵蓋 International League 與 Pacific Coast League。

2026-09-12：12 場樣本的 observed／official attempts 為 61／61，overturned 為 30／30；`validate-phase0` 回傳 `phase0_gate_pass = true`。另新增單場 `official_counter_pass`，候選場次若漏掉事件會直接失敗，不得靠挑選 aggregate comparison 規避。延長賽只作 parser／ledger regression protection，不納入主要 policy 研究。

## Answer

Phase 0 最低資料可行性驗收已完成。完整場次表、歷史 `hfABSFlag` 限制與後續缺口見 `reports/phase0_feasibility.md`。Legal Opportunity 的 technical outage／post-replay-review 排除、擴大歷史代表性與 Phase 1 baseline 分別延續於 Issue 07。
