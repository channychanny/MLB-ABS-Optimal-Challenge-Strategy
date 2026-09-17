# Phase 0 Hardening 規格

## 背景

既有原型能擷取 Challenge 並重建 ledger，但曾允許零事件或缺少 Savant 的比賽被誤判為通過，也缺少可執行的跨年度 gate、完整 opportunity population、provenance 與防洩漏契約。

## 範圍

- 單場 audit fail-closed。
- 2023–2026 rule regime 自動解析與 provisional 狀態。
- Legal／Reasonable／Attempt／Overturn 分層。
- 來源與輸入 hash。
- 跨年度 cohort、延長賽與官方 aggregate gate。
- 決策前 features 與事後 labels 分離。
- 主要 opportunity population 固定為第 1–9 局；延長賽不列為 Phase 0 必要樣本。

## 非範圍

- WP／RE 正式模型。
- Dynamic Programming、Monte Carlo 或 RRA 結果。
- 自動宣稱歷史 provisional 規則已確認。
- 延長賽 Challenge policy、refill value 或 RRA。

## 完成定義

只有跨年度資料與官方比較也完成、且 `validate-phase0` 回傳 `phase0_gate_pass = true` 時，整個 effort 才可標為 resolved。
