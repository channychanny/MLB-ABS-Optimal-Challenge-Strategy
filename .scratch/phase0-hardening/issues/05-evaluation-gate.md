# 05 — 建立跨年度驗收與評估契約

Type: task  
Status: resolved

## 驗收條件

- 版本化 cohort、延長賽與官方 aggregate 門檻。
- 官方比較依 requirements 重算，不信任輸入的舊 `pass`。
- opportunity dataset 明列決策前可用 features 與 label-only 欄位。
- 文件定義 temporal split、grouping、calibration 與 counterfactual 防洩漏規則。

## Answer

已完成 `validation.py`、`config/phase0_gate.json`、`model_input_contract` 與 `docs/evaluation_design.md`。
