from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "outputs"

EMBED_LABELS = {
    "emb_43": "图谱表征-核心企业协同强度",
    "emb_0": "图谱表征-产业链邻近性",
    "emb_19": "图谱表征-区域聚集度",
    "emb_60": "图谱表征-创新扩散势能",
    "emb_37": "图谱表征-供应链耦合深度",
    "emb_6": "图谱表征-风险隔离度",
    "emb_57": "图谱表征-业务稳定性",
    "emb_38": "图谱表征-场景落地密度",
    "emb_18": "图谱表征-链位穿透能力",
    "emb_10": "图谱表征-网络中心影响力",
    "emb_33": "图谱表征-上下游连接广度",
    "emb_20": "图谱表征-跨区域协同潜力",
    "emb_5": "图谱表征-技术协作活跃度",
    "emb_4": "图谱表征-链内互补性",
    "emb_25": "图谱表征-关系稳定性",
}

STRUCTURED_LABELS = {
    "graph_chain_degree": "图谱产业链连接数",
    "graph_region_degree": "图谱区域连接数",
    "graph_risk_event_count": "图谱风险事件数",
    "graph_patent_degree": "图谱专利连接数",
    "企业年龄": "企业年龄",
    "注册资本数值": "注册资本",
    "实缴资本数值": "实缴资本",
    "参保人数数值": "参保人数",
    "天眼评分数值": "天眼评分",
    "经营范围长度": "经营范围长度",
    "注册地址长度": "注册地址长度",
    "上游关键词命中数": "上游关键词命中数",
    "中游关键词命中数": "中游关键词命中数",
    "下游关键词命中数": "下游关键词命中数",
    "panel_patent_growth": "专利增长率",
    "panel_patent_avg": "专利平均活跃度",
    "panel_patent_trend_slope": "专利趋势斜率",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return default
    return text


def parse_float(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def pick_latest_profile(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    latest: dict[str, tuple[float, dict[str, str]]] = {}
    for row in rows:
        company_id = clean_text(row.get("统一社会信用代码"))
        if not company_id:
            continue
        year = parse_float(row.get("年份")) or -math.inf
        previous = latest.get(company_id)
        if previous is None or year >= previous[0]:
            latest[company_id] = (year, row)
    return {company_id: row for company_id, (_, row) in latest.items()}


def top_counter(rows: list[dict[str, Any]], key: str, limit: int = 8) -> list[dict[str, Any]]:
    counter = Counter(clean_text(row.get(key), "未标注") for row in rows)
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def feature_label(feature_name: str) -> str:
    if feature_name in STRUCTURED_LABELS:
        return STRUCTURED_LABELS[feature_name]
    if feature_name.startswith("emb_"):
        return EMBED_LABELS.get(feature_name, f"图谱表征维度{feature_name.split('_')[-1]}")
    return feature_name


def rewrite_shap_text(text: str) -> str:
    if not text:
        return text
    for raw_name, label in EMBED_LABELS.items():
        text = text.replace(f"图嵌入特征{raw_name}", label)
        text = text.replace(f"图嵌入特征 {raw_name}", label)
        text = text.replace(raw_name, label)
    return text


def build_demo_level(rank: int) -> str:
    if rank <= 10:
        return "A"
    if rank <= 20:
        return "B"
    if rank <= 30:
        return "C"
    return "D"


def build_level_distribution(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts = Counter(row[key] for row in rows)
    return [{"name": level, "count": counts.get(level, 0)} for level in ["A", "B", "C", "D"]]


@dataclass
class DemoRepository:
    companies: list[dict[str, Any]]
    company_map: dict[str, dict[str, Any]]
    summary: dict[str, Any]

    @classmethod
    def load(cls) -> "DemoRepository":
        prediction_rows = read_csv_rows(OUTPUT_DIR / "model_results" / "xgboost_fusion_predictions.csv")
        pipeline_rows = read_csv_rows(OUTPUT_DIR / "low_altitude_pipeline" / "企业主表.csv")
        feature_rows = read_csv_rows(OUTPUT_DIR / "model_results" / "white_list_feature_matrix.csv")
        master_rows = read_csv_rows(OUTPUT_DIR / "master_panel_results" / "39家企业画像总表.csv")
        static_rows = read_csv_rows(OUTPUT_DIR / "master_panel_results" / "39家企业画像静态总表.csv")
        importance_rows = read_csv_rows(OUTPUT_DIR / "model_results" / "xgboost_fusion_feature_importance.csv")
        fusion_report = read_json(OUTPUT_DIR / "model_results" / "xgboost_fusion_report.json")
        graphsage_report = read_json(OUTPUT_DIR / "graphsage" / "graphsage_report.json")

        static_codes = {
            clean_text(row.get("统一社会信用代码"))
            for row in static_rows
            if clean_text(row.get("统一社会信用代码"))
        }
        prediction_rows = [row for row in prediction_rows if clean_text(row.get("统一社会信用代码")) in static_codes]

        pipeline_map = {
            clean_text(row.get("统一社会信用代码")): row
            for row in pipeline_rows
            if clean_text(row.get("统一社会信用代码")) in static_codes
        }
        feature_map = {
            clean_text(row.get("统一社会信用代码")): row
            for row in feature_rows
            if clean_text(row.get("统一社会信用代码")) in static_codes
        }
        latest_master_map = pick_latest_profile(master_rows)
        static_map = {
            clean_text(row.get("统一社会信用代码")): row
            for row in static_rows
            if clean_text(row.get("统一社会信用代码"))
        }

        companies: list[dict[str, Any]] = []
        for row in prediction_rows:
            company_id = clean_text(row.get("统一社会信用代码"))
            pipeline = pipeline_map.get(company_id, {})
            features = feature_map.get(company_id, {})
            master = latest_master_map.get(company_id, {})
            static = static_map.get(company_id, {})
            merged = {
                "company_id": company_id,
                "company_name": clean_text(row.get("公司名称")) or clean_text(static.get("公司名称")),
                "standard_name": clean_text(row.get("企业标准名")) or clean_text(static.get("企业标准名")),
                "original_white_list_level": clean_text(row.get("white_list_level"), "未分级"),
                "sample_label": clean_text(row.get("样本标记")) or clean_text(pipeline.get("样本标记"), "未知"),
                "true_label": clean_text(row.get("true_label"), "未知"),
                "graphsage_pred_label": clean_text(row.get("graphsage_pred_label"), "未知"),
                "xgb_pred_label": clean_text(row.get("xgb_fusion_pred_label"), "未知"),
                "xgb_fusion_score": parse_float(row.get("xgb_fusion_score")) or 0.0,
                "graphsage_score": parse_float(row.get("graphsage_score")) or 0.0,
                "city": clean_text(static.get("所属城市")) or clean_text(master.get("所属城市"), "未标注"),
                "district": clean_text(static.get("所属区县")) or clean_text(master.get("所属区县"), "未标注"),
                "chain_position": clean_text(static.get("整合后产业链环节")) or clean_text(pipeline.get("产业链环节"), "未标注"),
                "company_type": clean_text(static.get("企业类型标签")) or clean_text(pipeline.get("企业类型标签"), "未标注"),
                "company_size": clean_text(pipeline.get("企业规模"), "未标注"),
                "registered_capital": clean_text(pipeline.get("注册资本"), "未披露"),
                "insured_count": parse_int(pipeline.get("参保人数")),
                "credit_score": parse_float(pipeline.get("天眼评分")),
                "legal_representative": clean_text(pipeline.get("法定代表人"), "未披露"),
                "status": clean_text(pipeline.get("登记状态"), "未披露"),
                "website": clean_text(pipeline.get("官网"), "未披露"),
                "scope": clean_text(pipeline.get("经营范围")) or clean_text(static.get("经营范围"), "暂无经营范围信息"),
                "address": clean_text(pipeline.get("注册地址")) or clean_text(static.get("注册地址"), "暂无注册地址"),
                "chain_basis": clean_text(pipeline.get("产业链判定依据")) or clean_text(static.get("产业链判定依据"), "暂无产业链判定依据"),
                "data_source": clean_text(static.get("数据来源")) or clean_text(pipeline.get("数据来源"), "未披露"),
                "top_positive": rewrite_shap_text(clean_text(row.get("shap_top_positive"), "暂无 SHAP 正向解释")),
                "top_negative": rewrite_shap_text(clean_text(row.get("shap_top_negative"), "暂无 SHAP 负向解释")),
                "graph_chain_degree": parse_int(features.get("graph_chain_degree")) or 0,
                "graph_region_degree": parse_int(features.get("graph_region_degree")) or 0,
                "graph_risk_event_count": parse_int(features.get("graph_risk_event_count")) or 0,
                "graph_patent_degree": parse_int(features.get("graph_patent_degree")) or 0,
                "enterprise_age": parse_float(features.get("企业年龄")),
                "macro_gdp_latest": parse_float(features.get("地区生产总值_当年价格_亿元_全市_latest")) or parse_float(static.get("地区生产总值_当年价格_亿元_全市")),
                "macro_per_gdp_latest": parse_float(features.get("人均地区生产总值_元_全市_latest")) or parse_float(static.get("人均地区生产总值_元_全市")),
                "macro_high_tech_latest": parse_float(features.get("国家级高新技术企业数_个_全市_latest")) or parse_float(static.get("国家级高新技术企业数_个_全市")),
                "macro_patent_auth_latest": parse_float(features.get("发明专利授权数_件_全市_latest")) or parse_float(static.get("发明专利授权数_件_全市")),
                "patent_total": parse_int(static.get("专利总量")),
                "patent_recent_3y": parse_int(static.get("近3年发明申请量")),
                "patent_breadth": parse_float(static.get("技术领域广度")),
            }
            companies.append(merged)

        companies.sort(
            key=lambda item: (
                item["xgb_fusion_score"],
                item["graphsage_score"],
                item["graph_patent_degree"],
                -(item["graph_risk_event_count"]),
                item["insured_count"] or 0,
                item["company_name"],
            ),
            reverse=True,
        )

        for idx, company in enumerate(companies, start=1):
            company["demo_rank"] = idx
            company["display_rank_label"] = f"#{idx}"
            company["demo_white_list_level"] = build_demo_level(idx)
            company["score_bucket"] = cls._score_bucket(idx)
            company["generated_report"] = cls._generate_report(company)

        top10 = companies[:10]
        risk_covered = sum(1 for company in companies if company["graph_risk_event_count"] > 0)
        hi_patent = sum(1 for company in companies if (company["graph_patent_degree"] or 0) >= 10)
        summary = {
            "sample_size": len(companies),
            "summary_cards": [
                {"label": "样本企业总数", "value": len(companies), "hint": "固定样本范围，仅保留抽样企业"},
                {"label": "A/B/C/D 分层", "value": "10 / 10 / 10 / 9", "hint": "按 39 家内部排序重分层"},
                {"label": "Top10 平均融合分数", "value": f"{sum(c['xgb_fusion_score'] for c in top10) / max(1, len(top10)):.6f}", "hint": "前十样本的平均融合分数"},
                {"label": "风险/专利覆盖", "value": f"{risk_covered} / {hi_patent}", "hint": "有风险事件企业数 / 高专利连接企业数"},
            ],
            "model_metrics": {
                "graphsage": {
                    "nodes": graphsage_report.get("num_nodes"),
                    "edges": graphsage_report.get("num_edges"),
                    "test_f1": graphsage_report.get("test_metrics", {}).get("f1"),
                    "test_auc": graphsage_report.get("test_metrics", {}).get("auc"),
                    "best_epoch": graphsage_report.get("best_epoch"),
                },
                "fusion": {
                    "train_size": fusion_report.get("train_rows"),
                    "positive_labels": fusion_report.get("positive_labels"),
                    "test_f1": fusion_report.get("test_metrics", {}).get("f1"),
                    "test_auc": fusion_report.get("test_metrics", {}).get("auc"),
                },
            },
            "demo_level_distribution": build_level_distribution(companies, "demo_white_list_level"),
            "city_distribution": top_counter(companies, "city"),
            "chain_distribution": top_counter(companies, "chain_position"),
            "top_features": [
                {
                    "feature": clean_text(item.get("feature")),
                    "label": feature_label(clean_text(item.get("feature"))),
                    "importance": parse_float(item.get("importance")) or 0.0,
                    "group": "graph" if clean_text(item.get("feature")).startswith("emb_") else "structured",
                }
                for item in importance_rows[:12]
            ],
            "top_companies": [
                {
                    "company_id": company["company_id"],
                    "company_name": company["company_name"],
                    "city": company["city"],
                    "demo_white_list_level": company["demo_white_list_level"],
                    "score": company["xgb_fusion_score"],
                }
                for company in companies[:10]
            ],
            "filter_options": {
                "cities": sorted({company["city"] for company in companies}),
                "levels": ["A", "B", "C", "D"],
                "chains": sorted({company["chain_position"] for company in companies}),
            },
        }
        company_map = {company["company_id"]: company for company in companies}
        return cls(companies=companies, company_map=company_map, summary=summary)

    @staticmethod
    def _score_bucket(rank: int) -> str:
        if rank <= 10:
            return "旗舰梯队"
        if rank <= 20:
            return "重点梯队"
        if rank <= 30:
            return "储备梯队"
        return "观察梯队"

    @staticmethod
    def _generate_report(company: dict[str, Any]) -> str:
        return (
            f"{company['company_name']}在样本企业中排序 {company['demo_rank']}，"
            f"分层等级为 {company['demo_white_list_level']} 类，融合分数 {company['xgb_fusion_score']:.6f}，"
            f"GraphSAGE 分数 {company['graphsage_score']:.6f}。"
            f"企业位于{company['city']}{company['district']}，处于{company['chain_position']}环节，"
            f"图谱侧表现为产业链连接 {company['graph_chain_degree']}、区域连接 {company['graph_region_degree']}、"
            f"风险事件 {company['graph_risk_event_count']}、专利连接 {company['graph_patent_degree']}。"
            f"主要正向因素包括：{company['top_positive']}。"
            f"主要约束因素包括：{company['top_negative']}。"
        )

    def list_companies(self, params: dict[str, list[str]] | None = None) -> dict[str, Any]:
        params = params or {}
        search = clean_text(params.get("search", [""])[0]).lower()
        level = clean_text(params.get("level", [""])[0])
        city = clean_text(params.get("city", [""])[0])
        chain = clean_text(params.get("chain", [""])[0])

        filtered = []
        for company in self.companies:
            matches_search = not search or search in company["company_name"].lower() or search in company["company_id"].lower()
            matches_level = not level or company["demo_white_list_level"] == level
            matches_city = not city or company["city"] == city
            matches_chain = not chain or company["chain_position"] == chain
            if matches_search and matches_level and matches_city and matches_chain:
                filtered.append(company)

        return {
            "total": len(filtered),
            "items": [self._company_list_item(company) for company in filtered],
        }

    def list_all_companies(self) -> dict[str, Any]:
        return {
            "total": len(self.companies),
            "items": [self._company_list_item(company) for company in self.companies],
        }

    def get_company_detail(self, company_id: str) -> dict[str, Any] | None:
        company = self.company_map.get(company_id)
        if not company:
            return None
        return {
            "basic_info": {
                "company_id": company["company_id"],
                "company_name": company["company_name"],
                "standard_name": company["standard_name"],
                "city": company["city"],
                "district": company["district"],
                "chain_position": company["chain_position"],
                "company_type": company["company_type"],
                "company_size": company["company_size"],
                "registered_capital": company["registered_capital"],
                "insured_count": company["insured_count"],
                "credit_score": company["credit_score"],
                "legal_representative": company["legal_representative"],
                "status": company["status"],
                "website": company["website"],
                "address": company["address"],
                "chain_basis": company["chain_basis"],
                "data_source": company["data_source"],
            },
            "model_info": {
                "demo_rank": company["demo_rank"],
                "display_rank_label": company["display_rank_label"],
                "demo_white_list_level": company["demo_white_list_level"],
                "original_white_list_level": company["original_white_list_level"],
                "score_bucket": company["score_bucket"],
                "xgb_fusion_score": company["xgb_fusion_score"],
                "xgb_pred_label": company["xgb_pred_label"],
                "graphsage_score": company["graphsage_score"],
                "graphsage_pred_label": company["graphsage_pred_label"],
                "sample_label": company["sample_label"],
                "true_label": company["true_label"],
                "top_positive": company["top_positive"],
                "top_negative": company["top_negative"],
            },
            "graph_snapshot": {
                "chain_degree": company["graph_chain_degree"],
                "region_degree": company["graph_region_degree"],
                "risk_event_count": company["graph_risk_event_count"],
                "patent_degree": company["graph_patent_degree"],
            },
            "macro_snapshot": {
                "macro_gdp_latest": company["macro_gdp_latest"],
                "macro_per_gdp_latest": company["macro_per_gdp_latest"],
                "macro_high_tech_latest": company["macro_high_tech_latest"],
                "macro_patent_auth_latest": company["macro_patent_auth_latest"],
                "enterprise_age": company["enterprise_age"],
                "patent_total": company["patent_total"],
                "patent_recent_3y": company["patent_recent_3y"],
                "patent_breadth": company["patent_breadth"],
            },
            "scope": company["scope"],
            "generated_report": company["generated_report"],
        }

    def export_static_payloads(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "companies": self.list_all_companies(),
            "company_details": {
                company["company_id"]: self.get_company_detail(company["company_id"])
                for company in self.companies
            },
        }

    @staticmethod
    def _company_list_item(company: dict[str, Any]) -> dict[str, Any]:
        return {
            "demo_rank": company["demo_rank"],
            "display_rank_label": company["display_rank_label"],
            "company_id": company["company_id"],
            "company_name": company["company_name"],
            "city": company["city"],
            "chain_position": company["chain_position"],
            "demo_white_list_level": company["demo_white_list_level"],
            "original_white_list_level": company["original_white_list_level"],
            "score_bucket": company["score_bucket"],
            "xgb_fusion_score": company["xgb_fusion_score"],
            "graphsage_score": company["graphsage_score"],
            "risk_events": company["graph_risk_event_count"],
        }
