from __future__ import annotations

import argparse
import getpass
import os
import re
from pathlib import Path

import pandas as pd

URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

ROOT = Path("/Users/lyh/Desktop/competiton")
DRAG_DIR = Path(
    "/Users/lyh/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_ra709g6y9k2p22_cf37/temp/drag"
)
LOW_ALTITUDE_DIR = ROOT / "outputs" / "low_altitude_pipeline"

COMPANY_NODES_FILE = DRAG_DIR / "company_nodes.csv"
RISK_REL_FILE = DRAG_DIR / "rel_company_risk.csv"
CHAIN_REL_FILE = DRAG_DIR / "rel_company_chain.csv"
REGION_REL_FILE = DRAG_DIR / "rel_company_region.csv"
INTEGRATED_FILE = LOW_ALTITUDE_DIR / "产业链整合清单.csv"
MATCH_FILE = LOW_ALTITUDE_DIR / "企业-专利匹配表.csv"

NAME_NORMALIZE_RE = re.compile(r"\s+")
USCC_RE = re.compile(r"^[0-9A-Z]{18}$")


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def clean_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def normalize_name(value: object) -> str:
    text = clean_value(value) or ""
    text = NAME_NORMALIZE_RE.sub("", text)
    return text.lower()


def safe_int(value: object, default: int | None = None) -> int | None:
    text = clean_value(value)
    if text is None:
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float | None = None) -> float | None:
    text = clean_value(value)
    if text is None:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def load_company_nodes() -> pd.DataFrame:
    df = load_csv(COMPANY_NODES_FILE)
    df["source_row_index"] = range(len(df))
    df["company_id"] = df["id"].map(clean_value)
    df["company_name"] = df["name"].map(clean_value)
    df["chain_position"] = df["chain_position"].map(clean_value)
    df["city"] = df["city"].map(clean_value)
    df["patent_count"] = df["patent_count"].map(lambda v: safe_int(v, default=0) or 0)
    df["name_key"] = df["company_name"].map(normalize_name)
    return df


def load_integrated_companies() -> pd.DataFrame:
    df = load_csv(INTEGRATED_FILE)
    df["company_name"] = df["公司名称"].map(clean_value)
    df["standard_name"] = df["企业标准名"].map(clean_value)
    df["uscc"] = df["统一社会信用代码"].map(clean_value)
    df["name_key"] = df["company_name"].map(normalize_name)
    df["standard_name_key"] = df["standard_name"].map(normalize_name)
    return df


def build_company_lookup(company_nodes: pd.DataFrame, integrated: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}

    for _, row in integrated.iterrows():
        company_name = clean_value(row["company_name"])
        standard_name = clean_value(row["standard_name"])
        uscc = clean_value(row["uscc"])
        if company_name and uscc:
            lookup[normalize_name(company_name)] = uscc
        if standard_name and uscc:
            lookup[normalize_name(standard_name)] = uscc

    for _, row in company_nodes.iterrows():
        company_name = clean_value(row["company_name"])
        if not company_name:
            continue
        integ = choose_integrated_row(integrated, company_name)
        if integ is not None:
            uscc = clean_value(integ["uscc"])
            if uscc:
                lookup[normalize_name(company_name)] = uscc

    return lookup


def choose_integrated_row(integrated: pd.DataFrame, company_name: str | None) -> pd.Series | None:
    if not company_name:
        return None
    key = normalize_name(company_name)
    matches = integrated[
        (integrated["name_key"] == key) | (integrated["standard_name_key"] == key)
    ]
    if matches.empty:
        return None
    return matches.iloc[0]


def make_company_rows(company_nodes: pd.DataFrame, integrated: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, node in company_nodes.iterrows():
        node_id = clean_value(node["company_id"])
        company_name = clean_value(node["company_name"])
        integ = choose_integrated_row(integrated, company_name)
        uscc = None
        if integ is not None:
            uscc = clean_value(integ["uscc"])
        if not uscc and node_id and USCC_RE.match(node_id):
            uscc = node_id

        props: dict[str, object] = {
            "name": company_name,
            "source_company_id": node_id,
            "source_row_index": safe_int(node["source_row_index"]),
            "chain_position": clean_value(node["chain_position"]),
            "city": clean_value(node["city"]),
            "patent_count": safe_int(node["patent_count"], default=0) or 0,
        }

        if integ is not None:
            props.update(
                {
                    "standard_name": clean_value(integ["standard_name"]),
                    "uscc": uscc,
                    "district_name": clean_value(integ["所属区县"]),
                    "established_at": clean_value(integ["成立日期"]),
                    "org_type": clean_value(integ["企业(机构)类型"]),
                    "company_type_tag": clean_value(integ["企业类型标签"]),
                    "chain_reason": clean_value(integ["产业链判定依据"]),
                    "alias_names": clean_value(integ["曾用名"]),
                    "business_scope": clean_value(integ["经营范围"]),
                    "data_source": clean_value(integ["数据来源"]),
                    "tech_breadth": safe_float(integ["技术领域广度"]),
                    "first_patent_year": safe_int(integ["首次申请年份"]),
                    "latest_patent_year": safe_int(integ["最近申请年份"]),
                    "match_methods": clean_value(integ["匹配方式汇总"]),
                    "has_review_flag": clean_value(integ["是否存在人工复核记录"]),
                    "integration_note": clean_value(integ["整合说明"]),
                    "has_patent": clean_value(integ["是否有专利"]),
                    "integrated_chain_position": clean_value(integ["整合后产业链环节"]),
                }
            )
        elif uscc:
            props["uscc"] = uscc

        rows.append(
            {
                "company_id": uscc or node_id,
                "props": {k: v for k, v in props.items() if v is not None},
            }
        )
    return rows


def load_risk_rows(company_lookup: dict[str, str]) -> tuple[list[dict], list[dict]]:
    df = load_csv(RISK_REL_FILE)
    resolved_rows: list[dict] = []
    unresolved_rows: list[dict] = []
    skipped_rows = 0

    current_company_name: str | None = None
    for _, row in df.iterrows():
        raw_company_name = clean_value(row["company_name"])
        if raw_company_name:
            current_company_name = raw_company_name

        company_name = raw_company_name or current_company_name
        case_id = clean_value(row["case_id"])
        event_type = clean_value(row["type"])
        result = clean_value(row["result"])

        if not case_id:
            skipped_rows += 1
            continue

        record = {
            "company_name": company_name,
            "case_id": case_id,
            "props": {
                "case_id": case_id,
                "type": event_type,
                "result": result,
                "company_name": company_name,
                "source_file": "rel_company_risk.csv",
            },
        }

        company_id = company_lookup.get(normalize_name(company_name)) if company_name else None
        if company_id:
            record["company_id"] = company_id
            resolved_rows.append(record)
        else:
            unresolved_rows.append(record)

    if skipped_rows:
        print(f"skipped empty risk rows: {skipped_rows}")

    return resolved_rows, unresolved_rows


def load_simple_relation_rows(path: Path, target_column: str, node_label: str) -> tuple[list[dict], list[str]]:
    df = load_csv(path)
    rows: list[dict] = []
    unresolved: list[str] = []
    for _, row in df.iterrows():
        company_id = clean_value(row["company_id"])
        target = clean_value(row[target_column])
        if not company_id or not target:
            unresolved.append(str(row.to_dict()))
            continue
        rows.append(
            {
                "company_id": company_id,
                "target_name": target,
                "target_label": node_label,
                "props": {"name": target},
            }
        )
    return rows, unresolved


def create_constraints(driver, import_patents: bool = False) -> None:
    statements = [
        "CREATE CONSTRAINT company_company_uscc IF NOT EXISTS FOR (c:Company) REQUIRE c.company_id IS UNIQUE",
        "CREATE CONSTRAINT chain_position_name IF NOT EXISTS FOR (c:ChainPosition) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT region_name IF NOT EXISTS FOR (r:Region) REQUIRE r.name IS UNIQUE",
        "CREATE CONSTRAINT risk_case_id IF NOT EXISTS FOR (r:RiskCase) REQUIRE r.case_id IS UNIQUE",
    ]
    if import_patents:
        statements.extend(
            [
                "CREATE CONSTRAINT patent_application_no IF NOT EXISTS FOR (p:Patent) REQUIRE p.application_no IS UNIQUE",
                "CREATE CONSTRAINT city_name IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE",
                "CREATE CONSTRAINT chain_segment_name IF NOT EXISTS FOR (s:ChainSegment) REQUIRE s.name IS UNIQUE",
                "CREATE CONSTRAINT ipc_code IF NOT EXISTS FOR (i:IPC) REQUIRE i.code IS UNIQUE",
            ]
        )

    with driver.session(database=DATABASE) as session:
        for statement in statements:
            session.run(statement)


def import_companies(driver, company_rows: list[dict]) -> None:
    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    SET c += row.props
    """
    with driver.session(database=DATABASE) as session:
        session.run(query, rows=company_rows)


def import_chain_positions(driver) -> int:
    df = load_csv(CHAIN_REL_FILE)
    company_nodes = load_company_nodes()
    integrated = load_integrated_companies()
    rows = []
    for idx, row in df.iterrows():
        source_index = idx
        chain_position = clean_value(row["chain_position"])
        if not chain_position or source_index >= len(company_nodes):
            continue
        company_name = clean_value(company_nodes.iloc[source_index]["company_name"])
        integ = choose_integrated_row(integrated, company_name)
        company_uscc = clean_value(integ["uscc"]) if integ is not None else None
        if not company_uscc:
            continue
        rows.append(
            {
                "company_id": company_uscc,
                "props": {
                    "name": chain_position,
                    "source_company_id": clean_value(row["company_id"]),
                },
            }
        )

    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    MERGE (p:ChainPosition {name: row.props.name})
    MERGE (c)-[:BELONGS_TO_CHAIN]->(p)
    """
    with driver.session(database=DATABASE) as session:
        session.run(query, rows=rows)
    return len(rows)


def import_regions(driver) -> int:
    df = load_csv(REGION_REL_FILE)
    company_nodes = load_company_nodes()
    integrated = load_integrated_companies()
    rows = []
    for idx, row in df.iterrows():
        source_index = idx
        region = clean_value(row["region"])
        if not region or source_index >= len(company_nodes):
            continue
        company_name = clean_value(company_nodes.iloc[source_index]["company_name"])
        integ = choose_integrated_row(integrated, company_name)
        company_uscc = clean_value(integ["uscc"]) if integ is not None else None
        if not company_uscc:
            continue
        rows.append(
            {
                "company_id": company_uscc,
                "props": {
                    "name": region,
                    "source_company_id": clean_value(row["company_id"]),
                },
            }
        )

    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    MERGE (r:Region {name: row.props.name})
    MERGE (c)-[:IN_REGION]->(r)
    """
    with driver.session(database=DATABASE) as session:
        session.run(query, rows=rows)
    return len(rows)


def import_risk_events(driver, risk_rows: list[dict]) -> None:
    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    MERGE (r:RiskCase {case_id: row.props.case_id})
    SET r += row.props
    MERGE (c)-[:HAS_RISK_EVENT]->(r)
    """
    with driver.session(database=DATABASE) as session:
        session.run(query, rows=risk_rows)


def import_patents_optional(driver) -> tuple[int, int]:
    if not MATCH_FILE.exists():
        return 0, 0

    df = load_csv(MATCH_FILE)
    patent_rows: list[dict] = []
    relation_rows: list[dict] = []
    patent_seen: set[str] = set()
    relation_seen: set[tuple[str, str]] = set()
    integrated = load_integrated_companies()

    for _, row in df.iterrows():
        app_no = clean_value(row["申请号"])
        uscc = clean_value(row["统一社会信用代码"])
        if not app_no or not uscc:
            continue

        if uscc not in set(integrated["uscc"]):
            continue

        ipc_codes = [code.strip() for code in str(row["IPC分类号"]).split(";") if code.strip() and code.strip().lower() != "nan"]

        if app_no not in patent_seen:
            patent_rows.append(
                {
                    "application_no": app_no,
                    "props": {
                        "application_no": app_no,
                        "name": clean_value(row["专利名称"]),
                        "application_year": safe_int(row["申请年份"]),
                        "patent_type": clean_value(row["专利类型"]),
                        "main_ipc": clean_value(row["IPC主分类号"]),
                        "applicant_name": clean_value(row["申请人"]),
                        "lead_applicant_name": clean_value(row["主导申请人名称"]),
                        "current_holder": clean_value(row["当前权利人"]),
                        "applicant_city": clean_value(row["申请人城市"]),
                        "match_method": clean_value(row["匹配方式"]),
                        "match_confidence": safe_float(row["匹配置信度"]),
                        "needs_review": clean_value(row["是否人工复核"]),
                        "review_reason": clean_value(row["人工复核原因"]),
                        "joint_application_flag": clean_value(row["多申请人标记"]),
                        "industry_university_flag": clean_value(row["是否产学研联合申请"]),
                        "collaboration_type": clean_value(row["合作关系五分类"]),
                    },
                    "ipc_codes": ipc_codes,
                }
            )
            patent_seen.add(app_no)

        relation_key = (uscc, app_no)
        if relation_key not in relation_seen:
            relation_rows.append(
                {
                    "company_uscc": uscc,
                    "application_no": app_no,
                    "props": {
                        "match_method": clean_value(row["匹配方式"]),
                        "match_confidence": safe_float(row["匹配置信度"]),
                        "needs_review": clean_value(row["是否人工复核"]),
                        "review_reason": clean_value(row["人工复核原因"]),
                    },
                }
            )
            relation_seen.add(relation_key)

    patent_query = """
    UNWIND $rows AS row
    MERGE (p:Patent {application_no: row.application_no})
    SET p += row.props
    FOREACH (ipc_code IN row.ipc_codes |
        MERGE (ipc:IPC {code: ipc_code})
        MERGE (p)-[:CLASSIFIED_AS]->(ipc)
    )
    """
    relation_query = """
    UNWIND $rows AS row
    MATCH (c:Company {uscc: row.company_uscc})
    MATCH (p:Patent {application_no: row.application_no})
    MERGE (c)-[r:APPLIED_FOR]->(p)
    SET r += row.props
    """

    with driver.session(database=DATABASE) as session:
        if patent_rows:
            session.run(patent_query, rows=patent_rows)
        if relation_rows:
            session.run(relation_query, rows=relation_rows)

    return len(patent_rows), len(relation_rows)


def clear_graph(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def summarize_inputs(company_nodes: pd.DataFrame, integrated: pd.DataFrame) -> None:
    print("=== Dry Run Summary ===")
    print(f"company_nodes rows: {len(company_nodes)}")
    print(f"integrated rows: {len(integrated)}")
    print(f"risk rows: {len(load_csv(RISK_REL_FILE))}")
    print(f"chain rel rows: {len(load_csv(CHAIN_REL_FILE))}")
    print(f"region rel rows: {len(load_csv(REGION_REL_FILE))}")
    if MATCH_FILE.exists():
        print(f"patent match rows: {len(load_csv(MATCH_FILE))}")
    print("=======================")


def verify_database(driver) -> None:
    queries = {
        "companies": "MATCH (c:Company) RETURN count(c) AS cnt",
        "chain_positions": "MATCH (c:ChainPosition) RETURN count(c) AS cnt",
        "regions": "MATCH (r:Region) RETURN count(r) AS cnt",
        "risk_cases": "MATCH (r:RiskCase) RETURN count(r) AS cnt",
        "chain_rels": "MATCH (:Company)-[r:BELONGS_TO_CHAIN]->(:ChainPosition) RETURN count(r) AS cnt",
        "region_rels": "MATCH (:Company)-[r:IN_REGION]->(:Region) RETURN count(r) AS cnt",
        "risk_rels": "MATCH (:Company)-[r:HAS_RISK_EVENT]->(:RiskCase) RETURN count(r) AS cnt",
    }
    with driver.session(database=DATABASE) as session:
        print("=== Post Import Check ===")
        for label, query in queries.items():
            result = session.run(query)
            cnt = result.single()["cnt"]
            print(f"{label}: {cnt}")
        print("=========================")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import low-altitude economy graph data into Neo4j.")
    parser.add_argument("--dry-run", action="store_true", help="Print source summaries without touching Neo4j.")
    parser.add_argument("--reset-graph", action="store_true", help="Clear the Neo4j database before importing.")
    parser.add_argument(
        "--import-patents",
        action="store_true",
        help="Also import the legacy company-patent graph from 企业-专利匹配表.csv.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the post-import Neo4j verification counts.",
    )
    return parser


def get_graph_database():
    from neo4j import GraphDatabase

    return GraphDatabase


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    company_nodes = load_company_nodes()
    integrated = load_integrated_companies()
    company_rows = make_company_rows(company_nodes, integrated)
    company_lookup = build_company_lookup(company_nodes, integrated)
    risk_rows, unresolved_risk_rows = load_risk_rows(company_lookup)

    summarize_inputs(company_nodes, integrated)
    print(f"resolved risk rows: {len(risk_rows)}")
    print(f"unresolved risk rows: {len(unresolved_risk_rows)}")

    if args.dry_run:
        if unresolved_risk_rows:
            print("unresolved risk examples:")
            for row in unresolved_risk_rows[:5]:
                print(row)
        return

    password = os.getenv("NEO4J_PASSWORD") or getpass.getpass("Neo4j password: ")
    GraphDatabase = get_graph_database()
    driver = GraphDatabase.driver(URI, auth=(USERNAME, password))
    try:
        driver.verify_connectivity()
        if args.reset_graph:
            clear_graph(driver)

        create_constraints(driver, import_patents=args.import_patents)
        import_companies(driver, company_rows)
        chain_count = import_chain_positions(driver)
        region_count = import_regions(driver)
        import_risk_events(driver, risk_rows)

        patent_counts = (0, 0)
        if args.import_patents:
            patent_counts = import_patents_optional(driver)

        print(f"Imported companies: {len(company_rows)}")
        print(f"Imported chain links: {chain_count}")
        print(f"Imported region links: {region_count}")
        print(f"Imported risk events: {len(risk_rows)}")
        if args.import_patents:
            print(f"Imported patents: {patent_counts[0]}")
            print(f"Imported company-patent relationships: {patent_counts[1]}")
        if unresolved_risk_rows:
            print(f"Unresolved risk rows skipped: {len(unresolved_risk_rows)}")
            for row in unresolved_risk_rows[:5]:
                print(row)
        if not args.skip_verify:
            verify_database(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
