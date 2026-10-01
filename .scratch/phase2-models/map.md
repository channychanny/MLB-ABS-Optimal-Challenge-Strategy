# Phase 2 自建研究模型工作地圖

Type: effort  
Status: open
Execution: deferred

## 排程更新（2026-09-21）

2026-09-21 決策：主要研究改用固定官方 WP／RE288，自建 WP 與全季 Dataset A 擴充改列延伸研究並暫緩。既有成果與資料契約保留；不截尾真實分差，不宣稱正式 Dynamic Policy／RRA 已完成。 本工作地圖改列延伸研究；03／04／05／08 均暫緩，已完成項目不改狀態。下方目標與首月結果保留歷史脈絡，不再是目前的執行順序。現行主線見 [新工作地圖](../official-wp-policy/map.md)。

## 延伸研究目標

依原 Phase 2 規劃，建立可重現的 Dataset A、RE24／RE288、校準後的 league-average WP，接回既有反事實估值。保留真實分差，解除 Phase 1 外部表格 ±5 的限制，但不保證稀有狀態的準確度。

## Issues

- [01 — Dataset A 建置與時間切分](issues/01-dataset-a.md)：resolved — 建置器及來源核對完成；2019 年真實 283 球通過，含 34 球大比分。
- [02 — 自算 RE 與九局平手邊界](issues/02-re-boundary.md)：resolved — Train-only 開發估計完成；正式全季 RE 與可靠邊界尚待資料覆蓋驗證。
- [03 — 歷史快照覆蓋與正式版本](issues/03-snapshot-version.md)：open／暫緩 — 全季取得計畫固定 12,029 場、36 月；首月 2019-03 全部 54 場／15,627 球通過、離線重播一致。待 Issue 08 儲存改善後接續月份，再驗證全季與正式版本；見 [首月報告](../../reports/archive/phase2/phase2_season_acquisition.md)。
- [04 — WP 訓練、校準與評估](issues/04-wp-model.md)：open／暫緩。
- [05 — 估值串接與官方比較](issues/05-integration.md)：open。
- [06 — 非投球判決與逐球對齊](issues/06-no-pitch-alignment.md)：resolved — Dataset A v2 事件與狀態核對完成；10 筆非投球排除、14 球保留不同來源編號。原 15 場逐球內容未變；179 項測試通過，固定來源離線重播 lock 一致。未知來源型態仍保守排除。

- [07 — 擴大樣本的判決碼與非投球事件差異](issues/07-expanded-alignment.md)：resolved — pitchout／missed_bunt 與 N 型非投球分類完成；同一 84 場通過，原 70 場完整資料指紋不變，192 項測試通過、離線 lock 一致。

- [08 — 全季資料的壓縮儲存與重播](issues/08-compressed-storage.md)：open。未壓縮容量估計超出保留空間後的預算；無損壓縮試算支持先改善儲存。

## 範圍

不訓練 ABS 翻判預測器，不建立 Future Opportunity／正式 RRA，不研究延長賽挑戰策略。Dataset A 的一般 MLB 勝負標籤與 Dataset B 的 Legal Opportunity 排除各自追蹤；後者尚未完整，仍阻擋正式 policy 評估。
