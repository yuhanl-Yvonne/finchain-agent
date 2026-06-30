from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover
    GraphDatabase = None


ROOT = Path("/Users/lyh/Desktop/competiton")
LOW_ALTITUDE_DIR = ROOT / "outputs" / "low_altitude_pipeline"
MASTER_PANEL_DIR = ROOT / "outputs" / "master_panel_results"
MODEL_DIR = ROOT / "outputs" / "model_results"
DRAG_DIR = Path(
    "/Users/lyh/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_ra709g6y9k2p22_cf37/temp/drag"
)

BASE_FILE = LOW_ALTITUDE_DIR / "企业主表.csv"
SAMPLE_PORTRAIT_FILE = LOW_ALTITUDE_DIR / "样本企业画像表.csv"
STATIC_39_FILE = MASTER_PANEL_DIR / "39家企业画像静态总表.csv"
PANEL_39_FILE = MASTER_PANEL_DIR / "39家企业画像总表.csv"
CHAIN_FILE = LOW_ALTITUDE_DIR / "产业链整合清单.csv"
UPSTREAM_FILE = LOW_ALTITUDE_DIR / "上游候选企业.csv"
PATENT_FILE = LOW_ALTITUDE_DIR / "有专利企业清单.csv"
PATENT_MATCH_FILE = LOW_ALTITUDE_DIR / "企业-专利匹配表.csv"
COMPANY_NODES_FILE = DRAG_DIR / "company_nodes.csv"
RISK_REL_FILE = DRAG_DIR / "rel_company_risk.csv"
CHAIN_REL_FILE = DRAG_DIR / "rel_company_chain.csv"
REGION_REL_FILE = DRAG_DIR / "rel_company_region.csv"
GRAPH_CACHE_FILE = MODEL_DIR / "neo4j_company_features.csv"
OUTPUT_FILE = MODEL_DIR / "white_list_feature_matrix.csv"
SUMMARY_FILE = MODEL_DIR / "white_list_feature_summary.json"

URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


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


def to_number(value: object) -> float:
    text = clean_text(value)
    if not text:
        return 0.0
    match = NUMBER_RE.search(text.replace(",", ""))
    if not match:
        return 0.0
    try:
        return float(match.group(0))
    except ValueError:
        return 0.0


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for col in df.columns:
        if col == "统一社会信用代码":
            df[col] = df[col].map(normalize_uscc)
        else:
            df[col] = df[col].map(clean_text)
    return df


def parse_year(value: object) -> float:
    text = clean_text(value)
    if not text:
        return float("nan")
    match = NUMBER_RE.search(text)
    return float(match.group(0)) if match else float("nan")


def load_graph_features() -> pd.DataFrame:
    if GraphDatabase is None:
        return load_local_graph_features()

    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        return load_local_graph_features()

    query = """
    MATCH (c:Company)
    OPTIONAL MATCH (c)-[:BELONGS_TO_CHAIN]->(cp:ChainPosition)
    WITH c, count(DISTINCT cp) AS chain_degree
    OPTIONAL MATCH (c)-[:IN_REGION]->(r:Region)
    WITH c, chain_degree, count(DISTINCT r) AS region_degree
    OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(risk:RiskCase)
    WITH c, chain_degree, region_degree, count(DISTINCT risk) AS risk_event_count
    OPTIONAL MATCH (c)-[:APPLIED_FOR]->(p:Patent)
    WITH c, chain_degree, region_degree, risk_event_count, count(DISTINCT p) AS patent_degree
    RETURN c.company_id AS company_id,
           chain_degree,
           region_degree,
           risk_event_count,
           patent_degree
    """

    driver = GraphDatabase.driver(URI, auth=(USERNAME, password))
    rows: list[dict] = []
    try:
        with driver.session(database=DATABASE) as session:
            for record in session.run(query):
                rows.append(
                    {
                        "统一社会信用代码": normalize_uscc(record["company_id"]),
                        "graph_chain_degree": int(record["chain_degree"] or 0),
                        "graph_region_degree": int(record["region_degree"] or 0),
                        "graph_risk_event_count": int(record["risk_event_count"] or 0),
                        "graph_patent_degree": int(record["patent_degree"] or 0),
                    }
                )
        graph_df = pd.DataFrame(rows)
        if not graph_df.empty:
            return graph_df
    except Exception:
        pass
    finally:
        driver.close()

    return load_local_graph_features()


def load_local_graph_features() -> pd.DataFrame:
    if not CHAIN_FILE.exists():
        return pd.DataFrame(columns=["统一社会信用代码"])

    integrated = read_csv(CHAIN_FILE)
    integrated["company_name_key"] = integrated.get("公司名称", "").map(clean_text).map(lambda x: x.replace(" ", "").lower())
    integrated["standard_name_key"] = integrated.get("企业标准名", "").map(clean_text).map(lambda x: x.replace(" ", "").lower())
    integrated["统一社会信用代码"] = integrated["统一社会信用代码"].map(normalize_uscc)

    name_to_uscc: dict[str, str] = {}
    for _, row in integrated.iterrows():
        uscc = normalize_uscc(row.get("统一社会信用代码", ""))
        if not uscc:
            continue
        for key in [row.get("company_name_key", ""), row.get("standard_name_key", "")]:
            key = clean_text(key)
            if key:
                name_to_uscc[key] = uscc

    rows_by_uscc: dict[str, dict[str, float | str]] = {}
    for _, row in integrated.iterrows():
        uscc = normalize_uscc(row.get("统一社会信用代码", ""))
        if not uscc:
            continue
        rows_by_uscc.setdefault(
            uscc,
            {
                "统一社会信用代码": uscc,
                "graph_chain_degree": 0.0,
                "graph_region_degree": 0.0,
                "graph_risk_event_count": 0.0,
                "graph_patent_degree": 0.0,
            },
        )
        if clean_text(row.get("产业链环节")):
            rows_by_uscc[uscc]["graph_chain_degree"] = 1.0
        if clean_text(row.get("所属城市")):
            rows_by_uscc[uscc]["graph_region_degree"] = 1.0

    if CHAIN_REL_FILE.exists():
        chain_rel = pd.read_csv(CHAIN_REL_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        company_nodes = pd.read_csv(COMPANY_NODES_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig") if COMPANY_NODES_FILE.exists() else pd.DataFrame()
        node_lookup = {}
        if not company_nodes.empty:
            for _, row in company_nodes.iterrows():
                node_lookup[clean_text(row.get("id"))] = name_to_uscc.get(clean_text(row.get("name")).replace(" ", "").lower(), "")
        for _, row in chain_rel.iterrows():
            source_id = clean_text(row.get("company_id"))
            uscc = normalize_uscc(source_id)
            if not uscc or len(uscc) != 18:
                uscc = node_lookup.get(source_id, "")
            if uscc and uscc in rows_by_uscc and clean_text(row.get("chain_position")):
                rows_by_uscc[uscc]["graph_chain_degree"] = max(float(rows_by_uscc[uscc]["graph_chain_degree"]), 1.0)

    if REGION_REL_FILE.exists():
        region_rel = pd.read_csv(REGION_REL_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        company_nodes = pd.read_csv(COMPANY_NODES_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig") if COMPANY_NODES_FILE.exists() else pd.DataFrame()
        node_lookup = {}
        if not company_nodes.empty:
            for _, row in company_nodes.iterrows():
                node_lookup[clean_text(row.get("id"))] = name_to_uscc.get(clean_text(row.get("name")).replace(" ", "").lower(), "")
        for _, row in region_rel.iterrows():
            source_id = clean_text(row.get("company_id"))
            uscc = normalize_uscc(source_id)
            if not uscc or len(uscc) != 18:
                uscc = node_lookup.get(source_id, "")
            if uscc and uscc in rows_by_uscc and clean_text(row.get("region")):
                rows_by_uscc[uscc]["graph_region_degree"] = max(float(rows_by_uscc[uscc]["graph_region_degree"]), 1.0)

    if RISK_REL_FILE.exists():
        risk_rel = pd.read_csv(RISK_REL_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        current_company_name = ""
        for _, row in risk_rel.iterrows():
            company_name = clean_text(row.get("company_name"))
            if company_name:
                current_company_name = company_name
            company_name = company_name or current_company_name
            case_id = clean_text(row.get("case_id"))
            if not company_name or not case_id:
                continue
            uscc = name_to_uscc.get(company_name.replace(" ", "").lower(), "")
            if uscc and uscc in rows_by_uscc:
                rows_by_uscc[uscc]["graph_risk_event_count"] = float(rows_by_uscc[uscc]["graph_risk_event_count"]) + 1.0

    if PATENT_MATCH_FILE.exists():
        patent_df = pd.read_csv(PATENT_MATCH_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        patent_df["统一社会信用代码"] = patent_df["统一社会信用代码"].map(normalize_uscc)
        patent_counts = (
            patent_df[patent_df["统一社会信用代码"] != ""]
            .groupby("统一社会信用代码")["申请号"]
            .nunique()
            .to_dict()
        )
        for uscc, count in patent_counts.items():
            rows_by_uscc.setdefault(
                uscc,
                {
                    "统一社会信用代码": uscc,
                    "graph_chain_degree": 0.0,
                    "graph_region_degree": 0.0,
                    "graph_risk_event_count": 0.0,
                    "graph_patent_degree": 0.0,
                },
            )
            rows_by_uscc[uscc]["graph_patent_degree"] = float(count)

    return pd.DataFrame(rows_by_uscc.values())


def add_common_features(df: pd.DataFrame) -> pd.DataFrame:
    if "成立日期" in df.columns:
        founded = pd.to_datetime(df["成立日期"], errors="coerce").dt.year
        df["成立年份"] = founded
        df["企业年龄"] = (2024 - founded + 1).clip(lower=0)
    else:
        df["成立年份"] = pd.NA
        df["企业年龄"] = 0

    df["注册资本数值"] = df.get("注册资本", "").map(to_number) if "注册资本" in df.columns else 0.0
    df["实缴资本数值"] = df.get("实缴资本", "").map(to_number) if "实缴资本" in df.columns else 0.0
    df["参保人数数值"] = df.get("参保人数", "").map(to_number) if "参保人数" in df.columns else 0.0
    df["天眼评分数值"] = df.get("天眼评分", "").map(to_number) if "天眼评分" in df.columns else 0.0

    if "注册地址" in df.columns:
        df["注册地址长度"] = df["注册地址"].fillna("").astype(str).str.len()
    else:
        df["注册地址长度"] = 0
    if "经营范围" in df.columns:
        scope = df["经营范围"].fillna("").astype(str)
        df["经营范围长度"] = scope.str.len()
        df["经营范围分号数"] = scope.str.count(";")
        df["经营范围中文逗号数"] = scope.str.count("，")
    else:
        df["经营范围长度"] = 0
        df["经营范围分号数"] = 0
        df["经营范围中文逗号数"] = 0
    if "曾用名" in df.columns:
        alias = df["曾用名"].fillna("").astype(str)
        df["曾用名长度"] = alias.str.len()
        df["曾用名分号数"] = alias.str.count(";")
    else:
        df["曾用名长度"] = 0
        df["曾用名分号数"] = 0

    if "数据来源" in df.columns:
        df["数据来源长度"] = df["数据来源"].fillna("").astype(str).str.len()
    else:
        df["数据来源长度"] = 0

    if "成立日期" in df.columns:
        founded = pd.to_datetime(df["成立日期"], errors="coerce").dt.year
        df["成立年份缺失"] = founded.isna().astype(int)
    else:
        df["成立年份缺失"] = 1

    for col in ["经度", "纬度", "adcode", "地级市代码"]:
        if col in df.columns:
            df[col + "_数值"] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col + "_数值"] = 0.0

    if "工业" in df.columns:
        pass

    return df


def build_panel_features(panel: pd.DataFrame) -> pd.DataFrame:
    year_cols = [col for col in panel.columns if col.startswith("年度发明申请量_")]
    for col in year_cols:
        panel[col] = pd.to_numeric(panel[col], errors="coerce").fillna(0)

    macro_cols = [
        "地区生产总值_当年价格_亿元_全市",
        "人均地区生产总值_元_全市",
        "科学技术支出_万元_全市",
        "固定资产投资_万元_全市",
        "常住人口_万人_全市",
        "第三产业占地区生产总值的比重_全市",
        "发明专利授权数_件_全市",
        "国家级高新技术企业数_个_全市",
        "技术合同成交额_万元_全市",
    ]
    for col in macro_cols:
        if col in panel.columns:
            panel[col] = pd.to_numeric(panel[col], errors="coerce")

    grouped = panel.groupby("统一社会信用代码", dropna=False)
    rows: list[dict] = []
    for uscc, group in grouped:
        row: dict[str, object] = {"统一社会信用代码": normalize_uscc(uscc)}
        if "年份" in group.columns:
            group_year = pd.to_numeric(group["年份"], errors="coerce")
            latest_idx = group_year.idxmax()
            latest = group.loc[latest_idx]
            row["panel_latest_year"] = float(group_year.max())
            row["panel_years_covered"] = int(group_year.nunique())
        else:
            latest = group.iloc[-1]
            row["panel_latest_year"] = 0.0
            row["panel_years_covered"] = len(group)

        for col in macro_cols:
            if col in group.columns:
                row[f"{col}_mean"] = float(group[col].mean())
                row[f"{col}_latest"] = float(pd.to_numeric(latest.get(col, 0), errors="coerce") or 0)
            else:
                row[f"{col}_mean"] = 0.0
                row[f"{col}_latest"] = 0.0

        if year_cols:
            yearly = group[year_cols].sum(axis=0)
            values = yearly.to_numpy(dtype=float)
            if len(values) >= 2:
                x = list(range(len(values)))
                x_mean = sum(x) / len(x)
                y_mean = float(values.mean())
                denom = sum((xi - x_mean) ** 2 for xi in x) or 1.0
                slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values)) / denom
                row["panel_patent_trend_slope"] = float(slope)
                row["panel_patent_growth"] = float(values[-1] - values[0])
                row["panel_patent_avg"] = float(values.mean())
                row["panel_patent_std"] = float(values.std())
            else:
                row["panel_patent_trend_slope"] = 0.0
                row["panel_patent_growth"] = 0.0
                row["panel_patent_avg"] = 0.0
                row["panel_patent_std"] = 0.0

        rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    base = read_csv(BASE_FILE)
    base = add_common_features(base)
    base["label_sample"] = (base["样本标记"] == "是").astype(int)

    feature_df = base[["统一社会信用代码", "公司名称", "企业标准名", "样本标记", "label_sample"]].copy()

    sources = []
    for path in [CHAIN_FILE, SAMPLE_PORTRAIT_FILE, STATIC_39_FILE, UPSTREAM_FILE, PATENT_FILE]:
        if path.exists():
            source = read_csv(path)
            if "统一社会信用代码" not in source.columns:
                continue
            source = add_common_features(source).drop_duplicates(subset=["统一社会信用代码"])
            sources.append(source)

    if PANEL_39_FILE.exists():
        panel = read_csv(PANEL_39_FILE)
        panel = build_panel_features(panel).drop_duplicates(subset=["统一社会信用代码"])
        sources.append(panel)

    graph_features = load_graph_features()
    if not graph_features.empty:
        sources.append(graph_features.drop_duplicates(subset=["统一社会信用代码"]))

    for source in sources:
        feature_df = feature_df.merge(source, on="统一社会信用代码", how="left", suffixes=("", "_dup"))
        dup_cols = [col for col in feature_df.columns if col.endswith("_dup")]
        for col in dup_cols:
            base_col = col[:-4]
            if base_col in feature_df.columns:
                feature_df[base_col] = feature_df[base_col].where(feature_df[base_col].notna(), feature_df[col])
            else:
                feature_df[base_col] = feature_df[col]
        if dup_cols:
            feature_df = feature_df.drop(columns=dup_cols)

    for col in feature_df.columns:
        if col in {"统一社会信用代码", "公司名称", "企业标准名", "样本标记"}:
            continue
        if feature_df[col].dtype == object:
            feature_df[col] = feature_df[col].map(clean_text)

    # 删除明显的标签泄漏字段和直接派生字段
    leakage_patterns = [
        "样本标记",
        "label_sample",
        "是否有专利",
        "专利总量",
        "累计发明申请量",
        "近3年发明申请量",
        "有专利申请年份数",
        "技术持续性",
        "技术领域广度",
        "联合申请占比",
        "首次申请年份",
        "最近申请年份",
        "年度发明申请量_",
        "匹配方式汇总",
        "是否存在人工复核记录",
        "整合说明",
        "产业链判定依据",
        "产业链环节",
        "整合后产业链环节",
        "企业类型标签",
        "企业(机构)类型",
        "样本分层标签",
        "成立年份分层",
        "专利活跃度分层",
        "是否上游候选_flag",
        "是否专利企业_flag",
        "has_potential_whitelist",
    ]
    drop_cols: list[str] = []
    for col in feature_df.columns:
        if any(pattern in col for pattern in leakage_patterns):
            drop_cols.append(col)
    feature_df = feature_df.drop(columns=sorted(set(drop_cols)), errors="ignore")

    text_keep = {"公司名称", "企业标准名"}
    for col in feature_df.columns:
        if col in {"统一社会信用代码"} | text_keep:
            continue
        if feature_df[col].dtype == object:
            feature_df[col] = feature_df[col].map(clean_text)

    numeric_cols = [
        col
        for col in feature_df.columns
        if col
        not in {
            "统一社会信用代码",
            "公司名称",
            "企业标准名",
            "样本标记",
        }
        and pd.api.types.is_numeric_dtype(feature_df[col])
    ]
    categorical_cols = [
        col
        for col in feature_df.columns
        if col
        not in {
            "统一社会信用代码",
            "公司名称",
            "企业标准名",
            "样本标记",
        }
        and not pd.api.types.is_numeric_dtype(feature_df[col])
    ]

    summary = {
        "rows": int(len(feature_df)),
        "positive_labels": int(base["label_sample"].sum()),
        "negative_labels": int((base["label_sample"] == 0).sum()),
        "numeric_features": numeric_cols,
        "categorical_features": categorical_cols,
        "sources": [str(BASE_FILE), str(SAMPLE_PORTRAIT_FILE), str(STATIC_39_FILE), str(PANEL_39_FILE), str(CHAIN_FILE), str(UPSTREAM_FILE), str(PATENT_FILE), str(GRAPH_CACHE_FILE)],
    }

    feature_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Feature matrix saved to: {OUTPUT_FILE}")
    print(f"Rows: {len(feature_df)}")
    print(f"Positive labels: {summary['positive_labels']}")
    print(f"Negative labels: {summary['negative_labels']}")


if __name__ == "__main__":
    main()
