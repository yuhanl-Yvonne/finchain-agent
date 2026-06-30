from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase


ROOT = Path("/Users/lyh/Desktop/competiton")
GRAPH_DIR = ROOT / "outputs" / "graphsage"

PRED_FILE = GRAPH_DIR / "graphsage_predictions.csv"
EMBED_FILE = GRAPH_DIR / "graphsage_embeddings.csv"
REPORT_FILE = GRAPH_DIR / "graphsage_report.json"

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
    pred_df = pd.read_csv(PRED_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    embed_df = pd.read_csv(EMBED_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))

    pred_df["company_id"] = pred_df["company_id"].map(normalize_uscc)
    embed_df["company_id"] = embed_df["company_id"].map(normalize_uscc)

    merged = pred_df.merge(embed_df, on="company_id", how="left")
    embedding_cols = [col for col in merged.columns if col.startswith("emb_")]

    rows: list[dict] = []
    for _, row in merged.iterrows():
        rows.append(
            {
                "company_id": row["company_id"],
                "graphsage_score": float(row["pred_prob"]),
                "graphsage_pred_label": clean_text(row["pred_label"]),
                "graphsage_true_label": clean_text(row["true_label"]),
                "graphsage_embedding": [float(row[col]) for col in embedding_cols if clean_text(row[col])],
                "graphsage_model": "GraphSAGE",
                "graphsage_best_epoch": int(report.get("best_epoch", -1)),
                "graphsage_test_f1": float(report.get("test_metrics", {}).get("f1", 0.0)),
                "graphsage_test_auc": float(report.get("test_metrics", {}).get("auc", 0.0)),
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
    SET c.graphsage_score = row.graphsage_score,
        c.graphsage_pred_label = row.graphsage_pred_label,
        c.graphsage_true_label = row.graphsage_true_label,
        c.graphsage_embedding = row.graphsage_embedding,
        c.graphsage_model = row.graphsage_model,
        c.graphsage_best_epoch = row.graphsage_best_epoch,
        c.graphsage_test_f1 = row.graphsage_test_f1,
        c.graphsage_test_auc = row.graphsage_test_auc
    RETURN count(c) AS updated_count
    """
    check_query = """
    MATCH (c:Company)
    WHERE c.graphsage_score IS NOT NULL
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
    print(f"Companies with graphsage_score: {check_count}")


if __name__ == "__main__":
    main()
