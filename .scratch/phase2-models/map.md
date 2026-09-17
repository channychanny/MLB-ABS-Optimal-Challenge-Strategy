# Phase 2 自建研究模型工作地圖

Type: effort  
Status: claimed

## 目標

依產品規格第 30 節，建立可重現的 Dataset A、RE24／RE288、校準後的 league-average WP，接回既有反事實估值。保留真實分差，解除 Phase 1 外部表格 ±5 的限制，但不保證稀有狀態的準確度。

## Issues

- [01 — Dataset A 建置與時間切分](issues/01-dataset-a.md)：resolved — 建置器及來源核對完成；2019 年真實 283 球通過，含 34 球大比分。
- [02 — 自算 RE 與九局平手邊界](issues/02-re-boundary.md)：resolved — Train-only 開發估計完成；正式全季 RE 與可靠邊界尚待資料覆蓋驗證。
- [03 — 歷史快照覆蓋與正式版本](issues/03-snapshot-version.md)：claimed — 快取、續跑與五年度樣本完成；20 場有 15 場／4,303 球通過，5 場對齊待處理。全季逐球覆蓋、正式版本未完成。
- [04 — WP 訓練、校準與評估](issues/04-wp-model.md)：open。
- [05 — 估值串接與官方比較](issues/05-integration.md)：open。
- [06 — 非投球判決與逐球對齊](issues/06-no-pitch-alignment.md)：open — 高優先；敬遠保送與計時器違規使原始三欄 join 不再普遍成立，需先處理再擴大正式資料。

## 範圍

不訓練 ABS 翻判預測器，不建立 Future Opportunity／正式 RRA，不研究延長賽挑戰策略。Dataset A 的一般 MLB 勝負標籤與 Dataset B 的 Legal Opportunity 排除各自追蹤；後者尚未完整，仍阻擋正式 policy 評估。
