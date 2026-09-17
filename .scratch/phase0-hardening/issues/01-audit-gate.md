# 01 — 強化單場 audit gate

Type: task  
Status: resolved

## 驗收條件

- 零 Challenge、缺少 Savant、join count mismatch、必要狀態缺失、無效 budget 或 provisional 規則均不可通過。
- 報告區分 `core_ledger_pass`、`statcast_join_pass`、`rule_regime_pass` 與 `phase0_game_pass`。
- Decision Side 與資格不明會失敗；僅守方 pitcher／catcher 無法細分時保留品質旗標但可通過。
- 至少一個官方延長賽 fixture。

## Answer

已完成並由 audit、ledger、extract 測試覆蓋；audit v2 將 team-level eligibility 與 exact role attribution 分離。官方 game 823488 fixture 可重現 5 次 Challenge 與終場額度。
