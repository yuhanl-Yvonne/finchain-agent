from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase


ROOT = Path("/Users/lyh/Desktop/competiton")
MODEL_DIR = ROOT / "outputs" / "model_results"

PRED_FILE = MODEL_DIR / "xgboost_fusion_predictions.csv"

URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_uscc(value: object) -> str:
    text = clean_text(value).upper().replace(" ", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def load_rows() -> list[dict]:
    df = pd.read_csv(PRED_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df["统一社会信用代码"] = df["统一社会信用代码"].map(normalize_uscc)

    rows: list[dict] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "company_id": row["统一社会信用代码"],
                "xgb_fusion_score": float(row["xgb_fusion_score"] or 0.0),
                "xgb_fusion_pred_label": clean_text(row["xgb_fusion_pred_label"]),
                "white_list_level": clean_text(row["white_list_level"]),
                "graphsage_score": float(row["graphsage_score"] or 0.0),
                "graphsage_pred_label": clean_text(row["graphsage_pred_label"]),
                "shap_top_positive": clean_text(row.get("shap_top_positive", "")),
                "shap_top_negative": clean_text(row.get("shap_top_negative", "")),
                "xgb_model": "XGBoostFusion",
            }
        )
    return rows


def main() -> None:
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is required.")

    rows = load_rows()
    driver = GraphDatabase.driver(URI, auth=(USERNAME, password))
    query = """
    UNWIND $rows AS row
    MATCH (c:Company {company_id: row.company_id})
    SET c.xgb_fusion_score = row.xgb_fusion_score,
        c.xgb_fusion_pred_label = row.xgb_fusion_pred_label,
        c.white_list_level = row.white_list_level,
        c.shap_top_positive = row.shap_top_positive,
        c.shap_top_negative = row.shap_top_negative,
        c.xgb_model = row.xgb_model
    RETURN count(c) AS updated_count
    """
    check_query = """
    MATCH (c:Company)
    WHERE c.xgb_fusion_score IS NOT NULL
    RETURN count(c) AS cnt
    """
    try:
        with driver.session(database=DATABASE) as session:
            updated_count = session.run(query, rows=rows).single()["updated_count"]
            check_count = session.run(check_query).single()["cnt"]
    finally:
        driver.close()

    print(f"Attempted rows: {len(rows)}")
    print(f"Updated company nodes: {updated_count}")
    print(f"Companies with xgb_fusion_score: {check_count}")


if __name__ == "__main__":
    main()
