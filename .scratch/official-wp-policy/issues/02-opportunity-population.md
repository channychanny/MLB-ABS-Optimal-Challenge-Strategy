# 02 — 機會母體與來源限制

Type: research  
Status: claimed

建立包含未挑戰判決的候選事件母體，分開記錄不利判決、規則資格、剩餘額度與 actual attempt。處理零額度及歷史策略的 censoring，不把 actual attempts 當成機會分布。

驗收需列出 technical outage／post-replay-review 的可取得證據與未知狀態；未知不能當成已排除。固定兩次 regime 與時間 cohort、維護完整開發樣本清單。來源不足時明確限定 estimand 與敏感度分析，未取得充分證據前維持 provisional_source_limitations，不宣稱完整 Legal population。

## 2026-09-23 來源盤點

Baseball Savant 官方定義明列 position-player pitching 及 technical issue 排除；MLB 2026 說明列 replay review 後不得再挑戰及技術問題暫停規則。現有 game feed／賽程介面尚未驗證有全場 outage 區間或逐球 replay 順序欄位；六場 feed 中未見非 ABS review type 或技術故障文字，只是「未找到跡證」，不能當成無故障證明。來源與 estimand 限制及本輪驗收步驟記於 [跨年度清冊報告](../../../reports/archive/phase2/official_wp_cross_year_sampling_plan.md)。

## 2026-09-24 逐球未知資格與切分規則

固定 24 場 feed 離線盤點有 78 個 `MJ` ABS review，但沒有可驗證全場停用區間／replay 逐球先後的完整來源；2,751 個候選的兩項資格均保留 `unknown`。沒有線索不能推定合法，完整 Legal population 尚未驗收。已預宣告 Dataset B 時間窗，39 場已知開發樣本一律隔離；新 game_pk、抽樣數量與開發清冊完整性尚待鎖定，不能稱 Validation／Test／External 資料已完成。見[資格與切分預備報告](../../../reports/archive/phase2/dataset_b_readiness_2026-09-24.md)。

## Comments

2026-09-24 至 25：Dataset B 96 場候選已取 feed，85 場完整逐球對齊、11 場官方計數不符；13,252 個暫定候選的 technical outage／replay 資格仍一律 `unknown`。官方規則文件確認這些排除條件，但本次公開 feed／CSV 未提供可驗證逐球區間；不得因沒有文字線索就升格為 Legal population。見[訓練前準備報告](../../../reports/archive/phase2/dataset_b_pretraining_preparation_2026-09-24.md)。

2026-09-29：6 場缺漏挑戰嚴格復原、5 場來源仍無法定位而排除；91 場／13,132 筆暫定有額度候選供限定觀察性模型輸入。technical outage／replay 資格仍 `unknown`，Issue 02 的完整 Legal Opportunity 驗收未完成。見[更新報告](../../../reports/archive/phase2/dataset_b_challenge_recovery_2026-09-29.md)。
