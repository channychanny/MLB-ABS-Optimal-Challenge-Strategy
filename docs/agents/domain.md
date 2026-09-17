# Domain docs

本專案採用 single-context domain documentation 配置。

## 探索前必讀

下列檔案存在時應先閱讀：

- 專案根目錄的 `CONTEXT.md`
- `docs/adr/` 下與工作範圍相關的 ADR

若上述檔案尚不存在，應直接繼續，不把缺少檔案視為錯誤。當術語或架構決策真正獲得釐清時，再透過 domain-modeling workflow 建立或更新它們。

視任務需要，同時查閱下列專案參考資料：

- `README.md`：目前範圍與執行指令
- `MLB ABS Optimal Challenge Strategy — 產品規格書.md`：研究目標及階段邊界
- `reports/phase0_feasibility.md`：已完成項目、研究發現及尚未關閉的 Gate 項目
- `docs/data_dictionary.md`：正規化資料語意
- `config/rule_regimes.json`：已確認及 provisional 的 Challenge 規則

## 配置

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-example-decision.md
│       └── ...
└── src/
```

## 詞彙

使用 `CONTEXT.md` 所定義的 domain terms，尤其應保持下列概念間的區別：

- Legal Challenge Opportunity
- Reasonable Challenge Candidate
- Challenge Attempt
- Successful Overturn
- Original umpire call
- ABS call
- Challenge budget 或 Challenges Remaining
- Required Recognition Accuracy
- Challenge Option Value

不得默默以同義詞取代既有術語。若必要概念缺漏或語意不明，應將其記錄為 domain-modeling 問題。

## 架構決策

變更既有設計前，先檢查相關 ADR。若提案與 ADR 衝突，必須明確指出衝突，不得默默覆寫決策。

下列專案層級決策應使用根目錄層級的 ADR：

- 資料來源語意
- Rule regime 解讀
- Dataset 與 join contract
- Model boundaries
- Phase-gate criteria
