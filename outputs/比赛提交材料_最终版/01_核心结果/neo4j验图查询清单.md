# Neo4j验图查询清单

## 1. 查看最终XGBoost融合高分企业
```cypher
MATCH (c:Company)
WHERE c.xgb_fusion_score IS NOT NULL
RETURN c.name AS company,
       c.company_id AS uscc,
       c.xgb_fusion_score AS score,
       c.white_list_level AS level,
       c.xgb_fusion_pred_label AS pred
ORDER BY c.xgb_fusion_score DESC
LIMIT 20;
```

## 2. 查看最终高分企业的产业链和区域
```cypher
MATCH (c:Company)
OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(p:ChainPosition)
OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
WHERE c.xgb_fusion_score IS NOT NULL
RETURN c.name AS company,
       c.xgb_fusion_score AS score,
       c.white_list_level AS level,
       p.name AS chain_position,
       r.name AS region
ORDER BY c.xgb_fusion_score DESC
LIMIT 20;
```

## 3. 查看最终高分企业风险数量
```cypher
MATCH (c:Company)
OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(risk:RiskCase)
WHERE c.xgb_fusion_score IS NOT NULL
RETURN c.name AS company,
       c.xgb_fusion_score AS score,
       c.white_list_level AS level,
       count(risk) AS risk_count
ORDER BY c.xgb_fusion_score DESC
LIMIT 20;
```

## 4. 查看最终高分企业的 SHAP 解释
```cypher
MATCH (c:Company)
WHERE c.xgb_fusion_score IS NOT NULL
RETURN c.name AS company,
       c.xgb_fusion_score AS score,
       c.white_list_level AS level,
       c.shap_top_positive AS shap_positive,
       c.shap_top_negative AS shap_negative
ORDER BY c.xgb_fusion_score DESC
LIMIT 20;
```

## 5. 查看某家企业的完整路径与 SHAP 解释
把下面企业名替换成你想看的公司：
```cypher
MATCH (c:Company {name:'深圳市大疆创新科技有限公司'})
OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(p:ChainPosition)
OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(risk:RiskCase)
RETURN c.name,
       c.company_id,
       c.xgb_fusion_score,
       c.white_list_level,
       c.shap_top_positive,
       c.shap_top_negative,
       p.name,
       r.name,
       collect(risk.case_id)[0..10] AS risk_cases;
```

## 6. 对比 GraphSAGE 与 XGBoost 融合分数
```cypher
MATCH (c:Company)
WHERE c.xgb_fusion_score IS NOT NULL
RETURN c.name,
       c.graphsage_score,
       c.xgb_fusion_score,
       c.white_list_level
ORDER BY c.xgb_fusion_score DESC
LIMIT 20;
```

## 7. 同时查看融合分数、SHAP 和图谱关系
```cypher
MATCH (c:Company)
OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(p:ChainPosition)
OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(risk:RiskCase)
WHERE c.xgb_fusion_score IS NOT NULL
RETURN c.name AS company,
       c.xgb_fusion_score AS score,
       c.white_list_level AS level,
       c.shap_top_positive AS shap_positive,
       c.shap_top_negative AS shap_negative,
       p.name AS chain_position,
       r.name AS region,
       count(risk) AS risk_count
ORDER BY c.xgb_fusion_score DESC
LIMIT 20;
```
