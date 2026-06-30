from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
MODEL_DIR = ROOT / "outputs" / "model_results"
LOW_ALTITUDE_DIR = ROOT / "outputs" / "low_altitude_pipeline"

PRED_FILE = MODEL_DIR / "white_list_predictions.csv"
FEATURE_FILE = MODEL_DIR / "white_list_feature_matrix.csv"
BASE_FILE = LOW_ALTITUDE_DIR / "企业主表.csv"
OUTPUT_FILE = MODEL_DIR / "top20_whitelist_recommendations.csv"

TOP_N = 20


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def to_number(value: object) -> float:
    text = clean_text(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def build_reason(row: pd.Series) -> str:
    parts: list[str] = []

    city = clean_text(row.get("所属城市"))
    if city:
        parts.append(f"位于{city}低空经济活跃区域")

    chain = clean_text(row.get("产业链环节"))
    if chain:
        parts.append(f"处于{chain}环节")

    ty_score = to_number(row.get("天眼评分"))
    if ty_score >= 80:
        parts.append("企业综合活跃度较高")
    elif ty_score >= 70:
        parts.append("企业综合基础较好")

    registered = clean_text(row.get("注册资本"))
    if registered:
        parts.append(f"注册资本为{registered}")

    staff = to_number(row.get("参保人数"))
    if staff >= 100:
        parts.append(f"参保人数达到{int(staff)}人")

    upstream = to_number(row.get("上游关键词命中数"))
    midstream = to_number(row.get("中游关键词命中数"))
    downstream = to_number(row.get("下游关键词命中数"))
    if max(upstream, midstream, downstream) > 0:
        if upstream >= midstream and upstream >= downstream:
            parts.append("上游技术关键词匹配较强")
        elif midstream >= upstream and midstream >= downstream:
            parts.append("中游应用制造关键词匹配较强")
        else:
            parts.append("下游服务运营关键词匹配较强")

    growth = to_number(row.get("panel_patent_growth"))
    if growth > 0:
        parts.append("近年创新活动呈上升趋势")

    reason = "；".join(parts[:4])
    return reason or "综合模型得分较高，建议优先人工核验"


def main() -> None:
    pred = pd.read_csv(PRED_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    feat = pd.read_csv(FEATURE_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    base = pd.read_csv(BASE_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    pred["predicted_probability"] = pd.to_numeric(pred["predicted_probability"], errors="coerce").fillna(0.0)

    merged = pred.merge(
        base[
            [
                "统一社会信用代码",
                "公司名称",
                "所属城市",
                "所属区县",
                "企业类型标签",
                "产业链环节",
                "产业链判定依据",
                "天眼评分",
                "企业规模",
                "参保人数",
                "注册资本",
                "经营范围",
                "企业简介",
                "官网",
            ]
        ],
        on=["统一社会信用代码", "公司名称"],
        how="left",
    ).merge(
        feat[
            [
                "统一社会信用代码",
                "上游关键词命中数",
                "下游关键词命中数",
                "中游关键词命中数",
                "panel_patent_growth",
                "panel_patent_avg",
                "panel_years_covered",
                "地区生产总值_当年价格_亿元_全市_latest",
                "人均地区生产总值_元_全市_latest",
            ]
        ],
        on="统一社会信用代码",
        how="left",
    )

    merged = merged.sort_values("predicted_probability", ascending=False).head(TOP_N).copy()
    merged["推荐顺位"] = range(1, len(merged) + 1)
    merged["推荐理由"] = merged.apply(build_reason, axis=1)
    merged["建议动作"] = "纳入候选白名单并进入图谱人工核验"

    output = merged[
        [
            "推荐顺位",
            "统一社会信用代码",
            "公司名称",
            "企业标准名",
            "所属城市",
            "所属区县",
            "企业类型标签",
            "产业链环节",
            "predicted_probability",
            "predicted_label",
            "true_label",
            "天眼评分",
            "企业规模",
            "参保人数",
            "注册资本",
            "上游关键词命中数",
            "中游关键词命中数",
            "下游关键词命中数",
            "panel_patent_growth",
            "panel_patent_avg",
            "panel_years_covered",
            "推荐理由",
            "建议动作",
            "产业链判定依据",
            "经营范围",
            "企业简介",
            "官网",
        ]
    ].rename(
        columns={
            "predicted_probability": "模型推荐分数",
            "predicted_label": "模型预测标签",
            "true_label": "当前样本标签",
        }
    )

    output.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Saved recommendations to: {OUTPUT_FILE}")
    print(output.head(10).to_string())


if __name__ == "__main__":
    main()
