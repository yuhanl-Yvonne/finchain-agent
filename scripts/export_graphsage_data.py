from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover
    GraphDatabase = None


ROOT = Path("/Users/lyh/Desktop/competiton")
MODEL_DIR = ROOT / "outputs" / "model_results"
LOW_ALTITUDE_DIR = ROOT / "outputs" / "low_altitude_pipeline"
GRAPH_DIR = ROOT / "outputs" / "graphsage"

FEATURE_FILE = MODEL_DIR / "white_list_feature_matrix.csv"
BASE_FILE = LOW_ALTITUDE_DIR / "企业主表.csv"

NODES_FILE = GRAPH_DIR / "company_nodes.csv"
FEATURES_FILE = GRAPH_DIR / "company_features.csv"
EDGES_FILE = GRAPH_DIR / "company_edges.csv"
META_FILE = GRAPH_DIR / "graph_data_meta.json"

URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
SEED = 42


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


def try_load_graph_groups() -> tuple[dict[str, str], dict[str, str]]:
    if GraphDatabase is None:
        return {}, {}
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        return {}, {}

    query = """
    MATCH (c:Company)
    OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
    OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(p:ChainPosition)
    RETURN c.company_id AS company_id, r.name AS region_name, p.name AS chain_name
    """

    region_map: dict[str, str] = {}
    chain_map: dict[str, str] = {}
    driver = GraphDatabase.driver(URI, auth=(USERNAME, password))
    try:
        with driver.session(database=DATABASE) as session:
            for row in session.run(query):
                company_id = normalize_uscc(row["company_id"])
                region_name = clean_text(row["region_name"])
                chain_name = clean_text(row["chain_name"])
                if company_id and region_name:
                    region_map[company_id] = region_name
                if company_id and chain_name:
                    chain_map[company_id] = chain_name
    except Exception:
        return {}, {}
    finally:
        driver.close()
    return region_map, chain_map


def stratified_split(labels: list[int]) -> tuple[set[int], set[int], set[int]]:
    rng = random.Random(SEED)
    pos = [i for i, y in enumerate(labels) if y == 1]
    neg = [i for i, y in enumerate(labels) if y == 0]
    rng.shuffle(pos)
    rng.shuffle(neg)

    def split_group(indices: list[int]) -> tuple[list[int], list[int], list[int]]:
        n = len(indices)
        n_train = int(n * 0.70)
        n_val = int(n * 0.15)
        n_test = n - n_train - n_val
        if n_val == 0 and n >= 3:
            n_val = 1
            n_train -= 1
        if n_test == 0 and n >= 3:
            n_test = 1
            n_train -= 1
        return (
            indices[:n_train],
            indices[n_train:n_train + n_val],
            indices[n_train + n_val:n_train + n_val + n_test],
        )

    pos_train, pos_val, pos_test = split_group(pos)
    neg_train, neg_val, neg_test = split_group(neg)
    train = set(pos_train + neg_train)
    val = set(pos_val + neg_val)
    test = set(pos_test + neg_test)
    return train, val, test


def build_edges(region_map: dict[str, str], chain_map: dict[str, str], company_ids: list[str]) -> pd.DataFrame:
    city_groups: dict[str, list[str]] = defaultdict(list)
    chain_groups: dict[str, list[str]] = defaultdict(list)

    for company_id in company_ids:
        region = clean_text(region_map.get(company_id))
        chain = clean_text(chain_map.get(company_id))
        if region:
            city_groups[region].append(company_id)
        if chain:
            chain_groups[chain].append(company_id)

    pair_types: dict[tuple[str, str], set[str]] = defaultdict(set)

    def add_pairs(groups: dict[str, list[str]], edge_type: str) -> None:
        for _, members in groups.items():
            members = sorted(set(members))
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pair_types[(members[i], members[j])].add(edge_type)

    add_pairs(city_groups, "shared_city")
    add_pairs(chain_groups, "shared_chain")

    rows = []
    for (src_id, dst_id), types in sorted(pair_types.items()):
        rows.append(
            {
                "src_company_id": src_id,
                "dst_company_id": dst_id,
                "edge_type": "|".join(sorted(types)),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    feature_df = pd.read_csv(FEATURE_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    base_df = pd.read_csv(BASE_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    feature_df["统一社会信用代码"] = feature_df["统一社会信用代码"].map(normalize_uscc)
    base_df["统一社会信用代码"] = base_df["统一社会信用代码"].map(normalize_uscc)

    label_map = base_df.set_index("统一社会信用代码")["样本标记"].map(clean_text).to_dict()
    city_map_local = base_df.set_index("统一社会信用代码")["所属城市"].map(clean_text).to_dict()
    chain_map_local = base_df.set_index("统一社会信用代码")["产业链环节"].map(clean_text).to_dict()

    region_map_graph, chain_map_graph = try_load_graph_groups()
    region_map = {company_id: region_map_graph.get(company_id) or city_map_local.get(company_id, "") for company_id in feature_df["统一社会信用代码"]}
    chain_map = {company_id: chain_map_graph.get(company_id) or chain_map_local.get(company_id, "") for company_id in feature_df["统一社会信用代码"]}

    labels = [1 if label_map.get(company_id, "") == "是" else 0 for company_id in feature_df["统一社会信用代码"]]
    train_idx, val_idx, test_idx = stratified_split(labels)

    node_rows = []
    for idx, row in feature_df.reset_index(drop=True).iterrows():
        company_id = row["统一社会信用代码"]
        node_rows.append(
            {
                "company_id": company_id,
                "company_name": clean_text(row.get("公司名称")),
                "node_index": idx,
                "label": labels[idx],
                "train_mask": 1 if idx in train_idx else 0,
                "val_mask": 1 if idx in val_idx else 0,
                "test_mask": 1 if idx in test_idx else 0,
            }
        )
    nodes_df = pd.DataFrame(node_rows)

    ignore_cols = {"统一社会信用代码", "公司名称", "企业标准名"}
    numeric_features = feature_df.drop(columns=[col for col in ignore_cols if col in feature_df.columns], errors="ignore")
    numeric_features = numeric_features.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    numeric_features.insert(0, "node_index", range(len(numeric_features)))

    edge_df = build_edges(region_map, chain_map, feature_df["统一社会信用代码"].tolist())
    node_index_map = nodes_df.set_index("company_id")["node_index"].to_dict()
    edge_df["src"] = edge_df["src_company_id"].map(node_index_map)
    edge_df["dst"] = edge_df["dst_company_id"].map(node_index_map)
    edge_df = edge_df.dropna(subset=["src", "dst"]).copy()
    edge_df["src"] = edge_df["src"].astype(int)
    edge_df["dst"] = edge_df["dst"].astype(int)
    edge_df = edge_df[["src", "dst", "edge_type", "src_company_id", "dst_company_id"]]

    nodes_df.to_csv(NODES_FILE, index=False, encoding="utf-8-sig")
    numeric_features.to_csv(FEATURES_FILE, index=False, encoding="utf-8-sig")
    edge_df.to_csv(EDGES_FILE, index=False, encoding="utf-8-sig")

    meta = {
        "seed": SEED,
        "num_nodes": int(len(nodes_df)),
        "num_edges": int(len(edge_df)),
        "positive_labels": int(sum(labels)),
        "train_size": int(nodes_df["train_mask"].sum()),
        "val_size": int(nodes_df["val_mask"].sum()),
        "test_size": int(nodes_df["test_mask"].sum()),
        "feature_dim": int(numeric_features.shape[1] - 1),
        "graph_sources": {
            "region_from_neo4j": len(region_map_graph),
            "chain_from_neo4j": len(chain_map_graph),
        },
    }
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved nodes to: {NODES_FILE}")
    print(f"Saved features to: {FEATURES_FILE}")
    print(f"Saved edges to: {EDGES_FILE}")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
