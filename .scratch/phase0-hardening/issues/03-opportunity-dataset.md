# 03 — 建立 Opportunity Dataset

Type: prototype  
Status: resolved

## 驗收條件

- 從完整逐球資料建立所有 Legal Opportunity，不只實際 Attempt。
- 區分 Reasonable Candidate、Attempt 與 Overturn。
- 重建當下剩餘額度並處理延長賽。
- 排除可明確辨識的 position player pitching。

## Answer

已新增完整逐球下載與 `build-opportunities` CLI；Reasonable v1 為 tri-state label，資料不足時保留 `null`。
