# 02 — 建立 rule resolver

Type: task  
Status: resolved

## 驗收條件

- CLI 不再以固定預設額度覆蓋各年度規則。
- 依 competition、season、日期、league 與 ABS format 唯一解析 regime。
- Full ABS 或無法唯一判定的歷史比賽 fail closed。

## Answer

已建立 `rules.py` 與版本化 `config/rule_regimes.json`。2024 年 6 月 25 日後、2025 Triple-A 與 2026 MLB 的 regulation-inning 規則已有官方來源；2023 與 2024 年 6 月 25 日前仍要求逐場 format 證據。官方 live feed 實際出現 `reviewType=MJ` 時，resolver 只把該場升級為 confirmed；人工 `--abs-format challenge` 沒有事件證據時仍維持 provisional。延長賽規則狀態獨立記錄，不阻擋主要研究。
