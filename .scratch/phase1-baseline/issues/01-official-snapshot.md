# 01 — 官方 RE288／WP Snapshot

Type: task  
Status: resolved

## 驗收條件

- 下載來源與原始回應可重播，hash 可驗證，預設拒絕覆寫。
- 正規化 288 個 RE 狀態與完整 regulation WP，拒絕重複與越界。
- 固定主隊視角、球數、分差範圍、來源年份宣告及九局平手值。
- 正式模型訓練年份不得與官方 baseline 年份混淆。

## Answer

2026-09-15：已取得 288 個 RE 與 5,184 個含球數 WP 狀態，含 11 個分差值；來源 bundle、hash、時戳及離線重播完成。已修正來源打方視角為主隊視角，使用 `savant-baseline-v2`，拒絕舊 v1。九局平手外生主隊值為 0.5；未估計延長賽策略。
