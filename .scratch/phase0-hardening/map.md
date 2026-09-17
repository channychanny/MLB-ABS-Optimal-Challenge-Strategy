# Phase 0 Hardening 工作地圖

Type: effort  
Status: resolved

## 目標

關閉 code review 發現的 Phase 0 關鍵風險，建立可重現、可驗收且能防止 data leakage 的資料管線。

## Issues

- [01 — 強化單場 audit gate](issues/01-audit-gate.md)：resolved — 零事件、Savant 缺失、count mismatch、必要狀態與 provisional 規則均不可通過。
- [02 — 建立 rule resolver](issues/02-rule-resolver.md)：resolved — CLI 依 metadata 與版本化設定解析 2023–2026 regime。
- [03 — 建立 opportunity dataset](issues/03-opportunity-dataset.md)：resolved — 完整逐球 Legal／Reasonable population 與野手登板排除。
- [04 — 建立 provenance manifest](issues/04-provenance.md)：resolved — 下載與本機輸入具 SHA-256 與來源資訊。
- [05 — 建立跨年度驗收與評估契約](issues/05-evaluation-gate.md)：resolved — 版本化 gate、官方誤差重算與 feature／label 分離。
- [06 — 完成跨年度資料驗收](issues/06-cross-year-validation.md)：resolved — 四個年度各 3 場 regulation-only 樣本通過，61 次 attempts／30 次 overturned 與官方 counter 完全一致。
- [07 — 建立 Phase 1 RE／WP Baseline](issues/07-phase1-baseline.md)：resolved — 2026-09-15 使用者同意官方 ±5 分限定驗收；自建模型訓練／校準轉入 Phase 2。

## 當前結果

Phase 0 已於 2026-09-12 通過：12 場跨年度樣本全數通過，官方 game-record comparison 的 attempts 與 overturn rate 誤差皆為 0。Phase 1 已限定驗收，目前工作見 [Phase 2 地圖](../phase2-models/map.md)；延長賽仍只作工程 regression protection，不屬主要研究。
