from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
CHAIN_FILE = ROOT / "outputs" / "low_altitude_pipeline" / "产业链整合清单.csv"
PORTRAIT_FILE = ROOT / "outputs" / "low_altitude_pipeline" / "样本企业画像表.csv"
GEO_FILE = ROOT / "outputs" / "geocode_results" / "产业链39家企业坐标表.csv"
MACRO_FILE = ROOT / "outputs" / "macro_match_results" / "39家企业_年份宏观匹配表.csv"
OUTPUT_DIR = ROOT / "outputs" / "master_panel_results"
OUTPUT_CSV = OUTPUT_DIR / "39家企业画像总表.csv"
OUTPUT_XLSX = OUTPUT_DIR / "39家企业画像总表.xlsx"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def main() -> None:
    chain = pd.read_csv(CHAIN_FILE)
    portrait = pd.read_csv(PORTRAIT_FILE)
    geo = pd.read_csv(GEO_FILE)
    macro = pd.read_csv(MACRO_FILE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    chain_base = chain[
        [
            "公司名称",
            "企业标准名",
            "统一社会信用代码",
            "所属城市",
            "所属区县",
            "成立日期",
            "企业(机构)类型",
            "企业类型标签",
            "整合后产业链环节",
            "产业链判定依据",
            "曾用名",
            "经营范围",
            "数据来源",
            "专利总量",
            "技术领域广度",
            "首次申请年份",
            "最近申请年份",
            "匹配方式汇总",
            "是否存在人工复核记录",
            "整合说明",
            "是否有专利",
        ]
    ].copy()

    portrait_cols = [
        "统一社会信用代码",
        "累计发明申请量",
        "近3年发明申请量",
        "有专利申请年份数",
        "技术持续性",
        "联合申请占比",
    ] + [col for col in portrait.columns if col.startswith("年度发明申请量_")]
    portrait_base = portrait[portrait_cols].drop_duplicates(subset=["统一社会信用代码"])

    geo_base = geo[
        [
            "统一社会信用代码",
            "注册地址",
            "高德返回格式化地址",
            "高德返回省",
            "高德返回市",
            "高德返回区县",
            "adcode",
            "经度",
            "纬度",
        ]
    ].drop_duplicates(subset=["统一社会信用代码"])

    macro = macro.rename(columns={"高德返回区县": "宏观匹配区县"})
    drop_cols = [col for col in macro.columns if col.endswith(".1")]
    macro = macro.drop(columns=drop_cols, errors="ignore")

    master = macro.merge(
        chain_base,
        on=["公司名称", "统一社会信用代码", "是否有专利"],
        how="left",
        suffixes=("", "_链表"),
    )
    master = master.merge(portrait_base, on="统一社会信用代码", how="left")
    master = master.merge(geo_base, on="统一社会信用代码", how="left", suffixes=("", "_坐标"))

    if "整合后产业链环节_链表" in master.columns and "整合后产业链环节" not in master.columns:
        master = master.rename(columns={"整合后产业链环节_链表": "整合后产业链环节"})

    ordered_cols = [
        "公司名称",
        "企业标准名",
        "统一社会信用代码",
        "年份",
        "整合后产业链环节",
        "企业类型标签",
        "企业(机构)类型",
        "是否有专利",
        "整合说明",
        "所属城市",
        "所属区县",
        "地级市代码",
        "年鉴省",
        "年鉴市",
        "注册地址",
        "高德返回格式化地址",
        "高德返回省",
        "高德返回市",
        "高德返回区县",
        "adcode",
        "经度",
        "纬度",
        "成立日期",
        "曾用名",
        "经营范围",
        "产业链判定依据",
        "数据来源",
        "专利总量",
        "累计发明申请量",
        "近3年发明申请量",
        "技术领域广度",
        "首次申请年份",
        "最近申请年份",
        "有专利申请年份数",
        "技术持续性",
        "联合申请占比",
        "匹配方式汇总",
        "是否存在人工复核记录",
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
    ordered_cols += [col for col in portrait_base.columns if col.startswith("年度发明申请量_")]

    master = master[ordered_cols].sort_values(by=["公司名称", "年份"])

    master.to_csv(OUTPUT_CSV, index=False)
    master.to_excel(OUTPUT_XLSX, index=False)

    print(f"Master panel saved to: {OUTPUT_CSV}")
    print(f"Rows: {len(master)}")


if __name__ == "__main__":
    main()
