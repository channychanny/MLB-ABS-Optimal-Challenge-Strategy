# Phase 1 — 官方 Baseline 原型

依產品規格第 30 節，增量建立官方查表、counterfactual 估值與合成決策流程。不是模型訓練、正式回測或研究結論。

## 資料契約

- 來源為 Baseball Savant Game Strategy Explorer；同次建置固定 RE288、含球數 WP、頁面方法說明與來源 manifest。
- WP 新查詢固定 `perspective=bat`；既有 `home` 查詢的原始 bundle 亦可重播，但回應仍以打方分差／打方勝率解讀。上半局反轉分差並取機率補數，下半局保持不變，再依 Decision Team 估值；見 ADR-0001。
- 主要估值只含第 1–9 局；第 10 局開始的官方平手值只作九局結束平手的外生邊界。
- 完整 RE288 應有 288 個狀態；WP 主範圍為 9 局 × 2 半局 × 3 出局 × 8 壘包 × 12 球數 × 11 分差。
- 官方頁面標示 2016–2025，RE 回應另有 `year=2025`。兩者都保存，不能推定所有 RE 列的實際估計窗口一致，也不能宣稱獨立 2025 test。
- 查表缺失、重複、非有限數、越界與不支援事件一律明示，不插補、不截尾、不取 observed delta 作替代。

## 狀態契約

- 純 called ball／strike；保送只處理被迫進壘、三振處理換半局與終場。
- 同球盜壘、暴投、捕逸、不死三振及其他額外 runner action 不自行推定 counterfactual，列為不支援。
- Decision Team 固定，不因換半局切換 WP 視角。
- RE 是未依再見截斷的半局得分 baseline；保送擠回分必須加上即時得分，第三出局後原半局剩餘 RE 為零。
- 真實小樣本只作狀態與查表 smoke test；只含 actual attempts，不代表完整 Legal Opportunity 母體。

## 交付

可離線重播的 CLI、可攜式小型測試 fixture、原型報告、個別 Issue 與未完成限制。正式模型仍被 Legal population 排除缺口及缺少專案 commit SHA 阻擋。
