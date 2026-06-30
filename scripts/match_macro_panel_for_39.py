from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
GEO_FILE = ROOT / "outputs" / "geocode_results" / "产业链39家企业坐标表.csv"
MACRO_FILE = ROOT / "1998～2024年中国城市统计年鉴地级市面板数据.dta"
OUTPUT_DIR = ROOT / "outputs" / "macro_match_results"
CITY_MAP_FILE = OUTPUT_DIR / "39家企业城市代码映射表.csv"
MATCHED_FILE = OUTPUT_DIR / "39家企业_年份宏观匹配表.csv"
MATCHED_XLSX = OUTPUT_DIR / "39家企业_年份宏观匹配表.xlsx"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def main() -> None:
    geo = pd.read_csv(GEO_FILE)
    macro = pd.read_stata(MACRO_FILE, convert_categoricals=False)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    geo["高德返回市"] = geo["高德返回市"].map(clean_text)
    macro["市"] = macro["市"].map(clean_text)
    macro["省"] = macro["省"].map(clean_text)

    city_map = (
        macro[macro["市"].isin(sorted(geo["高德返回市"].unique()))][["省", "市", "市代码"]]
        .drop_duplicates(subset=["市"])
        .sort_values(by="市")
        .rename(columns={"市": "高德返回市", "省": "年鉴省", "市代码": "地级市代码"})
    )

    geo_map = geo.merge(city_map, on="高德返回市", how="left")
    geo_map["adcode"] = geo_map["adcode"].astype(str).str.replace(".0", "", regex=False)
    city_map_export = geo_map[
        [
            "公司名称",
            "统一社会信用代码",
            "整合后产业链环节",
            "是否有专利",
            "高德返回市",
            "高德返回区县",
            "adcode",
            "地级市代码",
            "经度",
            "纬度",
        ]
    ].sort_values(by=["高德返回市", "整合后产业链环节", "公司名称"])
    city_map_export.to_csv(CITY_MAP_FILE, index=False)

    macro_keep_cols = [
        "年份",
        "省",
        "市",
        "市代码",
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
    macro_sub = macro[macro_keep_cols].copy()

    matched = geo_map.merge(
        macro_sub,
        left_on="地级市代码",
        right_on="市代码",
        how="left",
    )
    matched = matched.rename(
        columns={
            "省": "年鉴省",
            "市": "年鉴市",
        }
    )
    matched = matched[
        [
            "公司名称",
            "统一社会信用代码",
            "整合后产业链环节",
            "是否有专利",
            "高德返回市",
            "高德返回区县",
            "地级市代码",
            "经度",
            "纬度",
            "年份",
            "年鉴省",
            "年鉴市",
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
    ].sort_values(by=["公司名称", "年份"])

    matched.to_csv(MATCHED_FILE, index=False)
    matched.to_excel(MATCHED_XLSX, index=False)

    print(f"City map saved to: {CITY_MAP_FILE}")
    print(f"Macro matched rows: {len(matched)}")


if __name__ == "__main__":
    main()
