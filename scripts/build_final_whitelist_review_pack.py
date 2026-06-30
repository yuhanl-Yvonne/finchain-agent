from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
GRAPH_DIR = ROOT / "outputs" / "graphsage"
DELIVER_DIR = ROOT / "outputs" / "final_delivery"

TOP20_FILE = GRAPH_DIR / "top20_graphsage_recommendations.csv"
REVIEW_CSV = DELIVER_DIR / "最终白名单人工核验表.csv"
REVIEW_XLSX = DELIVER_DIR / "最终白名单人工核验表.xlsx"
QUERY_MD = DELIVER_DIR / "neo4j验图查询清单.md"


QUERY_TEXT = """# Neo4j验图查询清单

## 1. 查看GraphSAGE高分企业
```cypher
MATCH (c:Company)
WHERE c.graphsage_score IS NOT NULL
RETURN c.name AS company, c.company_id AS uscc, c.graphsage_score AS score, c.graphsage_pred_label AS pred
ORDER BY c.graphsage_score DESC
LIMIT 20;
```

## 2. 查看高分企业的产业链和区域
```cypher
MATCH (c:Company)
OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(p:ChainPosition)
OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
WHERE c.graphsage_score IS NOT NULL
RETURN c.name AS company, c.graphsage_score AS score, p.name AS chain_position, r.name AS region
ORDER BY c.graphsage_score DESC
LIMIT 20;
```

## 3. 查看高分企业风险数量
```cypher
MATCH (c:Company)
OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(risk:RiskCase)
WHERE c.graphsage_score IS NOT NULL
RETURN c.name AS company, c.graphsage_score AS score, count(risk) AS risk_count
ORDER BY c.graphsage_score DESC
LIMIT 20;
```

## 4. 查看某家企业的完整路径
把下面企业名替换成你想看的公司：
```cypher
MATCH (c:Company {name:'深圳市大疆创新科技有限公司'})
OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(p:ChainPosition)
OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(risk:RiskCase)
RETURN c.name, c.company_id, c.graphsage_score, p.name, r.name, collect(risk.case_id)[0..10] AS risk_cases;
```

## 5. 检查embedding是否写回
```cypher
MATCH (c:Company)
WHERE c.graphsage_embedding IS NOT NULL
RETURN c.name, size(c.graphsage_embedding) AS emb_dim, c.graphsage_score
ORDER BY c.graphsage_score DESC
LIMIT 20;
```
"""


def main() -> None:
    DELIVER_DIR.mkdir(parents=True, exist_ok=True)

    top20 = pd.read_csv(TOP20_FILE, encoding="utf-8-sig")
    review = top20.copy()
    review["图谱核验结果"] = ""
    review["风险判断"] = ""
    review["推荐结论"] = ""
    review["人工备注"] = ""

    ordered_cols = [
        "推荐顺位",
        "统一社会信用代码",
        "公司名称",
        "模型推荐分数",
        "模型预测标签",
        "当前样本标签",
        "所属城市",
        "所属区县",
        "企业类型标签",
        "产业链环节",
        "天眼评分",
        "企业规模",
        "参保人数",
        "注册资本",
        "推荐理由",
        "图谱核验结果",
        "风险判断",
        "推荐结论",
        "人工备注",
        "建议动作",
        "产业链判定依据",
        "经营范围",
    ]
    review = review[ordered_cols]

    review.to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")
    review.to_excel(REVIEW_XLSX, index=False)
    QUERY_MD.write_text(QUERY_TEXT, encoding="utf-8")

    print(f"Saved review csv to: {REVIEW_CSV}")
    print(f"Saved review xlsx to: {REVIEW_XLSX}")
    print(f"Saved query markdown to: {QUERY_MD}")


if __name__ == "__main__":
    main()
