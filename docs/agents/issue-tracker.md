# Issue tracker：本機 Markdown

本專案的 Issue 與規格以 Markdown 檔案存放於 `.scratch/`。

## 慣例

- 每項功能使用一個目錄：`.scratch/<feature-slug>/`
- 功能規格存放於 `.scratch/<feature-slug>/spec.md`
- 實作 Issue 個別存放於 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- Issue 編號從 `01` 開始
- 不得將所有實作 Ticket 合併成單一檔案
- 討論及後續紀錄附加於 `## Comments` 標題下

## 發布工作項目

當 skill 指示「發布至 issue tracker」時，在 `.scratch/<feature-slug>/` 下建立適當檔案，並視需要建立目錄。

當 skill 指示「取得相關 Ticket」時，讀取被引用的 Markdown 檔案。使用者通常會直接提供檔案路徑或 Issue 編號。

## Ticket 結構

Ticket 通常應包含：

- 標題
- 背景脈絡
- 範圍
- 驗收條件
- 相依關係（若適用）
- Comments（若適用）

## 與 Wayfinding 相容的配置

若工作流程需要工作地圖：

- Map：`.scratch/<effort>/map.md`
- Child ticket：`.scratch/<effort>/issues/<NN>-<slug>.md`
- Ticket 類型：使用 `Type:` 欄位，例如 `research`、`prototype`、`grilling` 或 `task`
- Ticket 狀態：使用 `Status:` 欄位，例如 `open`、`claimed` 或 `resolved`
- 相依關係：使用 `Blocked by: NN, NN` 欄位
- 認領：開始工作前將 `Status:` 改為 `claimed`
- 完成：將結果附加於 `## Answer`，把 `Status:` 改為 `resolved`，並在 Map 加入簡短的結果指標
