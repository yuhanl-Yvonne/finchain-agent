from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
ENTERPRISE_FILE = ROOT / "低空经济企业.xlsx"
SUPPLEMENT_ENTERPRISE_FILE = Path("/Users/lyh/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_ra709g6y9k2p22_cf37/temp/drag/30家企业.xlsx")
PATENT_FILE = Path("/Users/lyh/Desktop/6.24/最终版数据/Y专利数据带坐标.xlsx")
OUTPUT_DIR = ROOT / "outputs" / "low_altitude_pipeline"
OUTPUT_WORKBOOK = OUTPUT_DIR / "低空经济企业_专利匹配结果.xlsx"

YEARS = list(range(2010, 2025))
TARGET_SAMPLE_SIZE = 40
PRIORITY_CITIES = ["深圳市", "广州市", "东莞市", "珠海市", "佛山市"]
SUPPLEMENT_CITIES = {"深圳", "深圳市", "广州", "广州市", "珠海", "珠海市", "佛山", "佛山市", "东莞", "东莞市"}
HEAD_COMPANY_KEYWORDS = [
    "大疆",
    "亿航",
    "丰翼",
    "极飞",
    "道通",
    "联合飞机",
    "中科云图",
    "沃飞",
    "峰飞",
    "航景",
    "纵横",
    "美团",
    "顺丰",
    "小鹏",
]
UPSTREAM_KEYWORDS = [
    "电池",
    "电机",
    "芯片",
    "传感器",
    "雷达",
    "导航",
    "通信",
    "无线电",
    "线缆",
    "材料",
    "元器件",
    "锂离子",
    "储能",
    "螺旋桨",
    "发动机",
]
MIDSTREAM_KEYWORDS = [
    "无人机",
    "飞行器",
    "航空",
    "航天",
    "eVTOL",
    "飞行汽车",
    "智能无人飞行器",
    "航空器",
    "整机",
    "机巢",
    "航测",
    "测绘",
    "遥感",
    "系统集成",
    "控制系统",
]
DOWNSTREAM_KEYWORDS = [
    "物流",
    "配送",
    "巡检",
    "运营",
    "服务",
    "培训",
    "应用",
    "农业",
    "植保",
    "消防",
    "应急",
    "交通",
    "文旅",
    "飞行训练",
    "通用航空服务",
    "航空运营支持服务",
]
STRICT_UPSTREAM_KEYWORDS = [
    "芯片",
    "集成电路",
    "传感器",
    "雷达",
    "导航终端",
    "卫星导航",
    "无线电导航",
    "通信设备",
    "通信终端",
    "光电子器件",
    "电子元器件",
    "电池",
    "电机",
    "发动机",
    "螺旋桨",
    "机载设备",
    "电力电子",
    "新材料",
]
LEGAL_SUFFIXES = [
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "研究院",
    "集团",
    "公司",
]
MULTI_APPLICANT_PATTERN = re.compile(r"[;；,，、/]|\\bAND\\b|\\bAnd\\b|\\band\\b")
SPLIT_PATTERN = re.compile(r"[;；,，、]")


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text in {"", "-", "nan", "None"}:
        return ""
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\\s+", "", text)
    return text.lower()


def clean_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text in {"", "-", "nan", "None"}:
        return ""
    return text


def infer_short_name(company_name: str) -> str:
    short_name = company_name
    for suffix in LEGAL_SUFFIXES:
        if short_name.endswith(suffix) and len(short_name) > len(suffix) + 2:
            short_name = short_name[: -len(suffix)]
            break
    short_name = re.sub(r"^(广东省|广东|深圳市|深圳|广州市|广州|东莞市|东莞|珠海市|珠海|佛山市|佛山)", "", short_name)
    return short_name.strip("()（） ")


def normalize_parentheses(text: str) -> str:
    return text.replace("（", "(").replace("）", ")")


def classify_company_type(company_name: str, business_scope: str) -> str:
    text = f"{company_name} {business_scope}"
    if any(keyword in text for keyword in ["投资", "资本", "控股"]):
        return "投资发展类"
    if any(keyword in text for keyword in ["产业", "运营", "发展"]):
        return "产业运营类"
    if any(keyword in text for keyword in ["服务", "咨询", "平台", "管理"]):
        return "服务平台类"
    if any(keyword in text for keyword in ["科技", "技术", "智能", "无人", "航空", "研发"]):
        return "科技研发类"
    return "其他"


def classify_industry_chain(company_name: str, business_scope: str, industry_type: str) -> tuple[str, str]:
    text = f"{company_name} {business_scope} {industry_type}"

    def keyword_hits(keywords: list[str]) -> list[str]:
        return [keyword for keyword in keywords if keyword.lower() in text.lower()]

    upstream_hits = keyword_hits(UPSTREAM_KEYWORDS)
    midstream_hits = keyword_hits(MIDSTREAM_KEYWORDS)
    downstream_hits = keyword_hits(DOWNSTREAM_KEYWORDS)

    if midstream_hits:
        return "中游", "、".join(midstream_hits[:5])
    if upstream_hits and not downstream_hits:
        return "上游", "、".join(upstream_hits[:5])
    if downstream_hits:
        return "下游", "、".join(downstream_hits[:5])
    if upstream_hits:
        return "上游", "、".join(upstream_hits[:5])
    if any(keyword in text for keyword in ["制造业", "航空、航天器及设备制造", "智能消费设备制造"]):
        return "中游", "制造业/整机相关"
    if any(keyword in text for keyword in ["软件开发", "信息技术服务", "咨询", "管理服务"]):
        return "下游", "软件/服务相关"
    return "中游", "名称或经营范围含低空技术制造特征"


def age_bucket(established_at: pd.Timestamp) -> str:
    year = int(established_at.year)
    if year <= 2019:
        return "2010-2019"
    if year <= 2022:
        return "2020-2022"
    return "2023-2025"


def split_aliases(raw_aliases: object) -> list[str]:
    alias_text = clean_name(raw_aliases)
    if not alias_text:
        return []
    aliases = []
    for piece in SPLIT_PATTERN.split(alias_text):
        alias = piece.strip()
        if alias and alias != "-":
            aliases.append(alias)
    return aliases


def load_enterprises() -> pd.DataFrame:
    df = pd.read_excel(ENTERPRISE_FILE, sheet_name="高级搜索", header=1)
    keep_columns = [
        "公司名称",
        "统一社会信用代码",
        "成立日期",
        "所属城市",
        "所属区县",
        "注册地址",
        "曾用名",
        "经营范围",
        "企业(机构)类型",
        "天眼评分",
    ]
    enterprise = df[keep_columns].copy()
    enterprise["成立日期"] = pd.to_datetime(enterprise["成立日期"], errors="coerce")
    enterprise["企业标准名"] = enterprise["公司名称"].map(clean_name)
    enterprise["企业简称"] = enterprise["企业标准名"].map(infer_short_name)
    enterprise["企业类型标签"] = enterprise.apply(
        lambda row: classify_company_type(row["公司名称"], row["经营范围"]),
        axis=1,
    )
    enterprise["成立年份分层"] = enterprise["成立日期"].map(age_bucket)
    enterprise["样本标记"] = "否"
    enterprise["样本分层标签"] = ""
    enterprise["标准名归一化"] = enterprise["企业标准名"].map(normalize_text)
    enterprise["简称归一化"] = enterprise["企业简称"].map(normalize_text)
    chain_result = enterprise.apply(
        lambda row: classify_industry_chain(
            row["公司名称"],
            row["经营范围"],
            row["企业(机构)类型"],
        ),
        axis=1,
        result_type="expand",
    )
    enterprise["产业链环节"] = chain_result[0]
    enterprise["产业链判定依据"] = chain_result[1]
    return enterprise


def load_supplement_enterprises() -> pd.DataFrame:
    df = pd.read_excel(SUPPLEMENT_ENTERPRISE_FILE, sheet_name="批量查询-基础信息", header=1)
    rename_map = {
        "系统匹配企业名称": "公司名称",
        "企业地址": "注册地址",
    }
    df = df.rename(columns=rename_map)
    keep_columns = [
        "公司名称",
        "统一社会信用代码",
        "成立日期",
        "所属城市",
        "所属区县",
        "注册地址",
        "曾用名",
        "经营范围",
        "企业(机构)类型",
        "企业规模",
        "参保人数",
        "法定代表人",
        "登记状态",
        "注册资本",
        "实缴资本",
        "官网",
        "企业简介",
        "天眼评分",
    ]
    for column in keep_columns:
        if column not in df.columns:
            df[column] = pd.NA
    supplement = df[keep_columns].copy()
    supplement["成立日期"] = pd.to_datetime(supplement["成立日期"], errors="coerce")
    supplement["公司名称"] = supplement["公司名称"].map(clean_name)
    supplement["统一社会信用代码"] = supplement["统一社会信用代码"].map(clean_name)
    supplement["曾用名"] = supplement["曾用名"].map(clean_name)
    supplement["公司名称"] = supplement["公司名称"].map(normalize_parentheses)
    supplement["曾用名"] = supplement["曾用名"].map(normalize_parentheses)
    supplement = supplement.drop_duplicates(subset=["统一社会信用代码"], keep="first")
    supplement["数据来源"] = "天眼查补录30家"
    return supplement


def combine_enterprise_sources(base_enterprise: pd.DataFrame, supplement: pd.DataFrame) -> pd.DataFrame:
    enterprise = base_enterprise.copy()
    enterprise["企业规模"] = pd.NA
    enterprise["参保人数"] = pd.NA
    enterprise["法定代表人"] = pd.NA
    enterprise["登记状态"] = "存续"
    enterprise["注册资本"] = pd.NA
    enterprise["实缴资本"] = pd.NA
    enterprise["官网"] = pd.NA
    enterprise["企业简介"] = pd.NA
    enterprise["数据来源"] = "天眼查关键词企业"

    supplement_aligned = supplement.reindex(columns=enterprise.columns, fill_value=pd.NA)
    combined = pd.concat([enterprise, supplement_aligned], ignore_index=True)
    combined = combined.drop_duplicates(subset=["统一社会信用代码"], keep="first")
    combined["企业标准名"] = combined["公司名称"].map(clean_name).map(normalize_parentheses)
    combined["企业简称"] = combined["企业标准名"].map(infer_short_name)
    combined["企业类型标签"] = combined.apply(
        lambda row: classify_company_type(row["公司名称"], row["经营范围"]),
        axis=1,
    )
    combined["成立年份分层"] = combined["成立日期"].map(age_bucket)
    combined["样本标记"] = combined.get("样本标记", "否")
    combined["样本分层标签"] = combined.get("样本分层标签", "")
    combined["标准名归一化"] = combined["企业标准名"].map(normalize_text)
    combined["简称归一化"] = combined["企业简称"].map(normalize_text)
    chain_result = combined.apply(
        lambda row: classify_industry_chain(
            row["公司名称"],
            row["经营范围"],
            row["企业(机构)类型"],
        ),
        axis=1,
        result_type="expand",
    )
    combined["产业链环节"] = chain_result[0]
    combined["产业链判定依据"] = chain_result[1]
    return combined


def build_name_mapping(enterprise: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in enterprise.iterrows():
        uscc = row["统一社会信用代码"]
        standard_name = row["企业标准名"]

        records.append(
            {
                "统一社会信用代码": uscc,
                "企业标准名": standard_name,
                "原始名称": standard_name,
                "名称类型": "标准名",
                "归一化名称": normalize_text(standard_name),
            }
        )

        short_name = row["企业简称"]
        if short_name and short_name != standard_name:
            records.append(
                {
                    "统一社会信用代码": uscc,
                    "企业标准名": standard_name,
                    "原始名称": short_name,
                    "名称类型": "简称",
                    "归一化名称": normalize_text(short_name),
                }
            )

        for alias in split_aliases(row["曾用名"]):
            if alias != standard_name:
                records.append(
                    {
                        "统一社会信用代码": uscc,
                        "企业标准名": standard_name,
                        "原始名称": alias,
                        "名称类型": "曾用名",
                        "归一化名称": normalize_text(alias),
                    }
                )

        normalized_standard = normalize_parentheses(standard_name)
        if normalized_standard != standard_name:
            records.append(
                {
                    "统一社会信用代码": uscc,
                    "企业标准名": standard_name,
                    "原始名称": normalized_standard,
                    "名称类型": "人工修正名",
                    "归一化名称": normalize_text(normalized_standard),
                }
            )

    mapping = pd.DataFrame(records).drop_duplicates(
        subset=["统一社会信用代码", "归一化名称", "名称类型"]
    )
    return mapping


def add_patent_aliases(mapping: pd.DataFrame, patents: pd.DataFrame, enterprise: pd.DataFrame) -> pd.DataFrame:
    uscc_to_standard = enterprise.set_index("统一社会信用代码")["企业标准名"].to_dict()
    direct_patent_aliases = patents.loc[
        patents["统一社会信用代码"].notna() & patents["统一社会信用代码"].isin(uscc_to_standard),
        ["统一社会信用代码", "主导申请人名称"],
    ].copy()
    direct_patent_aliases["企业标准名"] = direct_patent_aliases["统一社会信用代码"].map(uscc_to_standard)
    direct_patent_aliases["原始名称"] = direct_patent_aliases["主导申请人名称"].map(clean_name)
    direct_patent_aliases["名称类型"] = "专利申请人名"
    direct_patent_aliases["归一化名称"] = direct_patent_aliases["原始名称"].map(normalize_text)
    direct_patent_aliases = direct_patent_aliases[
        direct_patent_aliases["归一化名称"] != ""
    ][["统一社会信用代码", "企业标准名", "原始名称", "名称类型", "归一化名称"]]
    combined = pd.concat([mapping, direct_patent_aliases], ignore_index=True)
    combined = combined.drop_duplicates(subset=["统一社会信用代码", "归一化名称", "名称类型"])
    return combined


def load_patents() -> pd.DataFrame:
    patents = pd.read_excel(PATENT_FILE)
    patents["申请年份"] = pd.to_numeric(patents["申请年份"], errors="coerce").astype("Int64")
    patents["匹配方式"] = ""
    patents["匹配置信度"] = 0.0
    patents["是否人工复核"] = "否"
    patents["人工复核原因"] = ""
    patents["主匹配企业"] = ""
    patents["主匹配企业信用代码"] = ""
    patents["多申请人标记"] = patents["申请人"].fillna("").astype(str).str.contains(MULTI_APPLICANT_PATTERN)
    return patents


def build_match_table(
    enterprise: pd.DataFrame, mapping: pd.DataFrame, patents: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    enterprise_lookup = enterprise.set_index("统一社会信用代码")

    exact_mapping = mapping.sort_values(
        by=["名称类型"],
        key=lambda s: s.map(
            {
                "标准名": 0,
                "专利申请人名": 1,
                "曾用名": 2,
                "简称": 3,
                "人工修正名": 4,
            }
        ).fillna(9),
    ).drop_duplicates(subset=["归一化名称"], keep="first")
    mapping_by_name = exact_mapping.set_index("归一化名称").to_dict("index")
    candidate_names = [
        (name, info["统一社会信用代码"], info["企业标准名"], info["名称类型"])
        for name, info in mapping_by_name.items()
        if name
    ]
    candidate_prefix_map: dict[str, list[tuple[str, str, str, str]]] = {}
    for candidate in candidate_names:
        prefix = candidate[0][:4]
        candidate_prefix_map.setdefault(prefix, []).append(candidate)

    matched_records = []
    review_records = []

    for _, patent in patents.iterrows():
        patent_dict = patent.to_dict()
        reasons = []
        matched = False
        method = ""
        confidence = 0.0
        uscc = clean_name(patent.get("统一社会信用代码"))
        matched_enterprise = None

        if uscc and uscc in enterprise_lookup.index:
            matched_enterprise = enterprise_lookup.loc[uscc]
            leader_name = normalize_text(patent.get("主导申请人名称"))
            current_holder = normalize_text(patent.get("当前权利人"))
            standard_name = normalize_text(matched_enterprise["企业标准名"])
            if current_holder and current_holder == standard_name and leader_name and leader_name != standard_name:
                method = "当前权利人代码直连"
                confidence = 0.98
            else:
                method = "信用代码直连"
                confidence = 1.0
            matched = True
        else:
            normalized_name = normalize_text(patent.get("主导申请人名称"))
            mapping_hit = mapping_by_name.get(normalized_name)
            if mapping_hit:
                matched_enterprise = enterprise_lookup.loc[mapping_hit["统一社会信用代码"]]
                if mapping_hit["名称类型"] == "曾用名":
                    method = "曾用名匹配"
                    confidence = 0.9
                else:
                    method = "名称精确匹配"
                    confidence = 0.95
                matched = True

        fuzzy_candidate_name = ""
        fuzzy_candidate_uscc = ""
        fuzzy_candidate_method = ""
        fuzzy_score = 0.0
        if not matched:
            normalized_name = normalize_text(patent.get("主导申请人名称"))
            if normalized_name:
                shortlist = candidate_prefix_map.get(normalized_name[:4], [])
                for candidate_name, candidate_uscc, candidate_standard_name, candidate_type in shortlist:
                    if abs(len(candidate_name) - len(normalized_name)) > 6:
                        continue
                    score = SequenceMatcher(None, normalized_name, candidate_name).ratio()
                    if score > fuzzy_score:
                        fuzzy_score = score
                        fuzzy_candidate_name = candidate_standard_name
                        fuzzy_candidate_uscc = candidate_uscc
                        fuzzy_candidate_method = f"相似名称候选({candidate_type})"

        applicant_name = clean_name(patent.get("申请人"))
        leader_raw = clean_name(patent.get("主导申请人名称"))
        current_holder_raw = clean_name(patent.get("当前权利人"))

        if patent_dict["多申请人标记"]:
            reasons.append("多申请人")
        if not uscc:
            reasons.append("专利缺失统一社会信用代码")
        if matched and method in {"曾用名匹配", "名称精确匹配"}:
            reasons.append("名称匹配建议复核")
        if not matched:
            reasons.append("未匹配到企业")
        if current_holder_raw and leader_raw and current_holder_raw != leader_raw:
            reasons.append("主导申请人与当前权利人不一致")
        if leader_raw and any(keyword in leader_raw for keyword in ["大学", "学院", "研究院", "实验室"]):
            reasons.append("主导申请人为高校或科研机构")
        if not matched and fuzzy_score >= 0.78:
            reasons.append(f"存在高相似候选:{round(fuzzy_score, 3)}")

        if matched:
            matched_record = {
                "统一社会信用代码": matched_enterprise.name,
                "公司名称": matched_enterprise["公司名称"],
                "企业标准名": matched_enterprise["企业标准名"],
                "申请号": patent.get("申请号"),
                "专利名称": patent.get("专利名称"),
                "申请年份": patent.get("申请年份"),
                "IPC主分类号": patent.get("IPC主分类号"),
                "申请人": applicant_name,
                "主导申请人名称": leader_raw,
                "当前权利人": current_holder_raw,
                "匹配方式": method,
                "匹配置信度": confidence,
                "是否人工复核": "是" if reasons else "否",
                "人工复核原因": "；".join(dict.fromkeys(reasons)),
                "主匹配企业": matched_enterprise["公司名称"],
                "主匹配企业信用代码": matched_enterprise.name,
                "专利类型": patent.get("专利类型"),
                "申请人城市": patent.get("申请人城市"),
                "IPC分类号": patent.get("IPC分类号"),
                "是否产学研联合申请": patent.get("是否产学研联合申请"),
                "合作关系五分类": patent.get("合作关系五分类"),
                "多申请人标记": "是" if patent_dict["多申请人标记"] else "否",
                "专利表统一社会信用代码": uscc,
            }
            matched_records.append(matched_record)

        should_review = matched and bool(reasons)
        if not matched and fuzzy_score >= 0.78:
            should_review = True
        if patent_dict["多申请人标记"] and matched:
            should_review = True

        if should_review:
            review_record = {
                "申请号": patent.get("申请号"),
                "专利名称": patent.get("专利名称"),
                "申请年份": patent.get("申请年份"),
                "申请人": applicant_name,
                "主导申请人名称": leader_raw,
                "当前权利人": current_holder_raw,
                "专利表统一社会信用代码": uscc,
                "建议匹配企业": matched_enterprise["公司名称"] if matched else fuzzy_candidate_name,
                "建议匹配信用代码": matched_enterprise.name if matched else fuzzy_candidate_uscc,
                "建议匹配方式": method if matched else fuzzy_candidate_method,
                "人工复核原因": "；".join(dict.fromkeys(reasons)),
            }
            review_records.append(review_record)

    matched_df = pd.DataFrame(matched_records)
    review_df = pd.DataFrame(review_records).drop_duplicates()

    if not matched_df.empty:
        patent_aliases = matched_df[["统一社会信用代码", "企业标准名", "主导申请人名称"]].copy()
        patent_aliases = patent_aliases.rename(columns={"主导申请人名称": "原始名称"})
        patent_aliases["名称类型"] = "专利申请人名"
        patent_aliases["归一化名称"] = patent_aliases["原始名称"].map(normalize_text)
        patent_aliases = patent_aliases[patent_aliases["归一化名称"] != ""]
        mapping = pd.concat([mapping, patent_aliases], ignore_index=True).drop_duplicates(
            subset=["统一社会信用代码", "归一化名称", "名称类型"]
        )

    return matched_df, review_df, mapping


def build_sample(enterprise: pd.DataFrame, matched_df: pd.DataFrame) -> pd.DataFrame:
    patent_counts = matched_df.groupby("统一社会信用代码")["申请号"].nunique().rename("专利总量")
    positive_counts = patent_counts[patent_counts > 0]
    high_threshold = positive_counts.quantile(0.75) if not positive_counts.empty else 0

    sample_base = enterprise.merge(patent_counts, on="统一社会信用代码", how="left")
    sample_base["专利总量"] = sample_base["专利总量"].fillna(0).astype(int)

    def patent_bucket(count: int) -> str:
        if count == 0:
            return "零专利"
        if count >= max(1, math.ceil(high_threshold)):
            return "高专利"
        return "中专利"

    sample_base["专利活跃度分层"] = sample_base["专利总量"].map(patent_bucket)
    sample_base["样本分层标签"] = sample_base.apply(
        lambda row: "|".join(
            [
                row["所属城市"],
                row["成立年份分层"],
                row["企业类型标签"],
                row["专利活跃度分层"],
            ]
        ),
        axis=1,
    )

    selected = []
    picked_codes = set()
    covered_labels = set()

    matched_priority = sample_base[sample_base["专利总量"] > 0].sort_values(
        by=["专利总量", "天眼评分", "成立日期"],
        ascending=[False, False, True],
    )
    for _, row in matched_priority.iterrows():
        code = row["统一社会信用代码"]
        if code in picked_codes:
            continue
        selected.append(row.to_dict())
        picked_codes.add(code)
        covered_labels.add(row["样本分层标签"])
        if len(selected) >= min(TARGET_SAMPLE_SIZE, len(matched_priority)):
            break

    for city in PRIORITY_CITIES:
        city_df = sample_base[sample_base["所属城市"] == city].sort_values(
            by=["专利总量", "天眼评分", "成立日期"],
            ascending=[False, False, True],
        )
        for _, row in city_df.iterrows():
            code = row["统一社会信用代码"]
            if code in picked_codes:
                continue
            if row["样本分层标签"] not in covered_labels:
                selected.append(row.to_dict())
                picked_codes.add(code)
                covered_labels.add(row["样本分层标签"])
            if len(selected) >= TARGET_SAMPLE_SIZE:
                break
        if len(selected) >= TARGET_SAMPLE_SIZE:
            break

    if len(selected) < TARGET_SAMPLE_SIZE:
        remaining = sample_base[~sample_base["统一社会信用代码"].isin(picked_codes)].sort_values(
            by=["所属城市", "专利总量", "天眼评分", "成立日期"],
            ascending=[True, False, False, True],
        )
        for _, row in remaining.iterrows():
            selected.append(row.to_dict())
            picked_codes.add(row["统一社会信用代码"])
            if len(selected) >= TARGET_SAMPLE_SIZE:
                break

    sample_df = pd.DataFrame(selected)
    sample_df["样本标记"] = "是"

    enterprise.loc[enterprise["统一社会信用代码"].isin(sample_df["统一社会信用代码"]), "样本标记"] = "是"
    sample_labels = sample_df.set_index("统一社会信用代码")["样本分层标签"].to_dict()
    enterprise["样本分层标签"] = enterprise["统一社会信用代码"].map(sample_labels).fillna("")

    return sample_df


def build_portrait(sample_df: pd.DataFrame, matched_df: pd.DataFrame) -> pd.DataFrame:
    patent_unique = matched_df.drop_duplicates(subset=["统一社会信用代码", "申请号"]).copy()
    annual = (
        patent_unique.groupby(["统一社会信用代码", "申请年份"])["申请号"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=YEARS, fill_value=0)
    )

    base_metrics = patent_unique.groupby("统一社会信用代码").agg(
        累计发明申请量=("申请号", "nunique"),
        首次申请年份=("申请年份", "min"),
        最近申请年份=("申请年份", "max"),
        技术领域广度=("IPC主分类号", lambda s: s.dropna().nunique()),
    )

    active_years = (
        patent_unique.groupby("统一社会信用代码")["申请年份"]
        .nunique()
        .rename("有专利申请年份数")
    )

    joint_ratio = (
        patent_unique.assign(
            联合申请标记=patent_unique["多申请人标记"].eq("是")
            | patent_unique["是否产学研联合申请"].astype(str).isin(["1", "是", "True"])
        )
        .groupby("统一社会信用代码")["联合申请标记"]
        .mean()
        .rename("联合申请占比")
    )

    portrait = sample_df.merge(base_metrics, on="统一社会信用代码", how="left")
    portrait = portrait.merge(active_years, on="统一社会信用代码", how="left")
    portrait = portrait.merge(joint_ratio, on="统一社会信用代码", how="left")
    portrait = portrait.merge(annual, on="统一社会信用代码", how="left")

    for year in YEARS:
        if year not in portrait.columns:
            portrait[year] = 0
        portrait[f"年度发明申请量_{year}"] = portrait[year].fillna(0).astype(int)
    portrait = portrait.drop(columns=YEARS, errors="ignore")

    portrait["累计发明申请量"] = portrait["累计发明申请量"].fillna(0).astype(int)
    portrait["首次申请年份"] = portrait["首次申请年份"].fillna(pd.NA).astype("Int64")
    portrait["最近申请年份"] = portrait["最近申请年份"].fillna(pd.NA).astype("Int64")
    portrait["有专利申请年份数"] = portrait["有专利申请年份数"].fillna(0).astype(int)
    portrait["技术领域广度"] = portrait["技术领域广度"].fillna(0).astype(int)
    portrait["联合申请占比"] = portrait["联合申请占比"].fillna(0).round(4)

    recent_years = [2022, 2023, 2024]
    portrait["近3年发明申请量"] = portrait[[f"年度发明申请量_{year}" for year in recent_years]].sum(axis=1)

    founded_year = portrait["成立日期"].dt.year.fillna(2025).astype(int)
    denominator = (2024 - founded_year + 1).clip(lower=1)
    portrait["技术持续性"] = (portrait["有专利申请年份数"] / denominator).round(4)

    return portrait[
        [
            "统一社会信用代码",
            "公司名称",
            "企业标准名",
            "所属城市",
            "所属区县",
            "成立日期",
            "企业类型标签",
            "产业链环节",
            "产业链判定依据",
            "成立年份分层",
            "专利活跃度分层",
            "样本分层标签",
            "专利总量",
            "累计发明申请量",
            "近3年发明申请量",
            "首次申请年份",
            "最近申请年份",
            "有专利申请年份数",
            "技术持续性",
            "技术领域广度",
            "联合申请占比",
        ]
        + [f"年度发明申请量_{year}" for year in YEARS]
    ].sort_values(by=["所属城市", "专利总量", "公司名称"], ascending=[True, False, True])


def build_patent_enterprise_list(enterprise: pd.DataFrame, matched_df: pd.DataFrame) -> pd.DataFrame:
    patent_counts = matched_df.groupby("统一社会信用代码").agg(
        专利总量=("申请号", "nunique"),
        首次申请年份=("申请年份", "min"),
        最近申请年份=("申请年份", "max"),
        技术领域广度=("IPC主分类号", lambda s: s.dropna().nunique()),
    )
    match_methods = (
        matched_df.groupby("统一社会信用代码")["匹配方式"]
        .apply(lambda s: "；".join(sorted(set(s.astype(str)))))
        .rename("匹配方式汇总")
    )
    review_flags = (
        matched_df.groupby("统一社会信用代码")["是否人工复核"]
        .apply(lambda s: "是" if (s == "是").any() else "否")
        .rename("是否存在人工复核记录")
    )

    result = enterprise.merge(patent_counts, on="统一社会信用代码", how="inner")
    result = result.merge(match_methods, on="统一社会信用代码", how="left")
    result = result.merge(review_flags, on="统一社会信用代码", how="left")
    result = result[result["专利总量"] > 0].copy()
    return result[
        [
            "公司名称",
            "企业标准名",
            "统一社会信用代码",
            "所属城市",
            "所属区县",
            "成立日期",
            "企业(机构)类型",
            "企业类型标签",
            "产业链环节",
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
        ]
    ].sort_values(by=["产业链环节", "专利总量", "公司名称"], ascending=[True, False, True])


def build_upstream_candidates(enterprise: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    def score_row(row: pd.Series) -> tuple[int, int, int]:
        text = f"{row.get('公司名称', '')} {row.get('经营范围', '')} {row.get('企业(机构)类型', '')}"
        strict_hits = sum(keyword in text for keyword in STRICT_UPSTREAM_KEYWORDS)
        downstream_hits = sum(keyword in text for keyword in DOWNSTREAM_KEYWORDS)
        mid_hits = sum(keyword in text for keyword in MIDSTREAM_KEYWORDS)
        return strict_hits, downstream_hits, mid_hits

    candidates = []
    for _, row in enterprise.iterrows():
        strict_hits, downstream_hits, mid_hits = score_row(row)
        if strict_hits == 0:
            continue
        text = f"{row.get('公司名称', '')} {row.get('经营范围', '')}"
        if any(keyword in text for keyword in ["无人机制造", "智能无人飞行器制造", "飞行训练", "通用航空服务"]):
            # Avoid treating obvious整机/运营主体 as upstream.
            if strict_hits < 4:
                continue
        candidates.append(
            {
                "公司名称": row["公司名称"],
                "统一社会信用代码": row["统一社会信用代码"],
                "所属城市": row["所属城市"],
                "企业类型标签": row["企业类型标签"],
                "上游关键词命中数": strict_hits,
                "下游关键词命中数": downstream_hits,
                "中游关键词命中数": mid_hits,
                "建议产业链环节": "上游",
                "建议判定依据": "、".join(
                    [keyword for keyword in STRICT_UPSTREAM_KEYWORDS if keyword in text][:6]
                ),
                "经营范围": row["经营范围"],
                "数据来源": row["数据来源"],
            }
        )

    candidate_df = pd.DataFrame(candidates)
    candidate_df = candidate_df.sort_values(
        by=["上游关键词命中数", "下游关键词命中数", "中游关键词命中数", "所属城市"],
        ascending=[False, True, True, True],
    )
    candidate_df = candidate_df.drop_duplicates(subset=["公司名称"]).head(limit)
    return candidate_df


def build_integrated_chain_list(
    patent_enterprise_df: pd.DataFrame, upstream_candidate_df: pd.DataFrame
) -> pd.DataFrame:
    integrated = patent_enterprise_df.copy()
    integrated["整合后产业链环节"] = integrated["产业链环节"]
    integrated["整合说明"] = "来自有专利企业清单"
    integrated["是否有专利"] = "是"

    upstream_lookup = upstream_candidate_df.set_index("公司名称")
    overlap_names = set(integrated["公司名称"]).intersection(set(upstream_lookup.index))

    for name in overlap_names:
        integrated.loc[integrated["公司名称"] == name, "整合后产业链环节"] = "上游"
        integrated.loc[integrated["公司名称"] == name, "整合说明"] = "有专利企业，且列入上游候选"
        integrated.loc[integrated["公司名称"] == name, "产业链判定依据"] = upstream_lookup.loc[name, "建议判定依据"]

    upstream_only = upstream_candidate_df[
        ~upstream_candidate_df["公司名称"].isin(integrated["公司名称"])
    ].copy()
    if not upstream_only.empty:
        upstream_only["企业标准名"] = upstream_only["公司名称"]
        upstream_only["所属区县"] = pd.NA
        upstream_only["成立日期"] = pd.NaT
        upstream_only["企业(机构)类型"] = pd.NA
        upstream_only["曾用名"] = pd.NA
        upstream_only["专利总量"] = 0
        upstream_only["技术领域广度"] = pd.NA
        upstream_only["首次申请年份"] = pd.NA
        upstream_only["最近申请年份"] = pd.NA
        upstream_only["匹配方式汇总"] = pd.NA
        upstream_only["是否存在人工复核记录"] = "否"
        upstream_only["产业链环节"] = "上游"
        upstream_only["产业链判定依据"] = upstream_only["建议判定依据"]
        upstream_only["整合后产业链环节"] = "上游"
        upstream_only["整合说明"] = "仅列入上游候选，当前未匹配到专利"
        upstream_only["是否有专利"] = "否"
        upstream_only = upstream_only.rename(columns={"建议判定依据": "上游判定依据"})
        upstream_only = upstream_only[
            [
                "公司名称",
                "企业标准名",
                "统一社会信用代码",
                "所属城市",
                "所属区县",
                "成立日期",
                "企业(机构)类型",
                "企业类型标签",
                "产业链环节",
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
                "整合后产业链环节",
                "整合说明",
                "是否有专利",
            ]
        ]
        integrated = pd.concat([integrated, upstream_only], ignore_index=True)

    order_map = {"上游": 0, "中游": 1, "下游": 2}
    integrated["排序键"] = integrated["整合后产业链环节"].map(order_map).fillna(9)
    integrated = integrated.sort_values(
        by=["排序键", "是否有专利", "专利总量", "公司名称"],
        ascending=[True, False, False, True],
    ).drop(columns=["排序键"])
    return integrated


def build_summary(enterprise: pd.DataFrame, patents: pd.DataFrame, matched_df: pd.DataFrame, review_df: pd.DataFrame, sample_df: pd.DataFrame) -> pd.DataFrame:
    direct = matched_df["匹配方式"].eq("信用代码直连").sum()
    current_holder = matched_df["匹配方式"].eq("当前权利人代码直连").sum()
    exact_name = matched_df["匹配方式"].eq("名称精确匹配").sum()
    alias_name = matched_df["匹配方式"].eq("曾用名匹配").sum()
    summary = [
        ("企业主表企业数", len(enterprise)),
        ("企业主表统一社会信用代码空值数", int(enterprise["统一社会信用代码"].isna().sum())),
        ("企业主表统一社会信用代码重复数", int(enterprise["统一社会信用代码"].duplicated().sum())),
        ("专利总记录数", len(patents)),
        ("专利表自带统一社会信用代码记录数", int(patents["统一社会信用代码"].notna().sum())),
        ("专利匹配成功记录数", len(matched_df)),
        ("专利匹配成功申请号数", int(matched_df["申请号"].nunique())),
        ("信用代码直连记录数", int(direct)),
        ("当前权利人代码直连记录数", int(current_holder)),
        ("名称精确匹配记录数", int(exact_name)),
        ("曾用名匹配记录数", int(alias_name)),
        ("人工复核池记录数", len(review_df)),
        ("未纳入企业范围的专利记录数", int(len(patents) - len(matched_df))),
        ("有专利企业数", int(matched_df["统一社会信用代码"].nunique())),
        ("样本企业数", len(sample_df)),
        ("样本中零专利企业数", int(sample_df["专利活跃度分层"].eq("零专利").sum())),
    ]
    return pd.DataFrame(summary, columns=["指标", "数值"])


def build_supplement_list(enterprise: pd.DataFrame, patents: pd.DataFrame) -> pd.DataFrame:
    enterprise_codes = set(enterprise["统一社会信用代码"].astype(str))
    enterprise_names = set(enterprise["企业标准名"].astype(str))

    patent_base = patents.copy()
    patent_base["主导申请人名称"] = patent_base["主导申请人名称"].map(clean_name)
    patent_base["统一社会信用代码"] = patent_base["统一社会信用代码"].map(clean_name)
    patent_base["申请人城市"] = patent_base["申请人城市"].map(clean_name)
    patent_base["当前权利人"] = patent_base["当前权利人"].map(clean_name)

    grouped = (
        patent_base.groupby(["主导申请人名称", "统一社会信用代码"], dropna=False)
        .agg(
            专利数=("申请号", "nunique"),
            首次申请年份=("申请年份", "min"),
            最近申请年份=("申请年份", "max"),
            IPC主分类号数=("IPC主分类号", lambda s: s.dropna().nunique()),
            申请人城市=("申请人城市", lambda s: s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else ""),
            当前权利人=("当前权利人", lambda s: s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else ""),
        )
        .reset_index()
    )

    grouped = grouped[
        grouped["主导申请人名称"].ne("")
        & ~grouped["主导申请人名称"].isin(enterprise_names)
        & ~grouped["统一社会信用代码"].isin(enterprise_codes)
    ].copy()

    grouped["是否头部关键词命中"] = grouped["主导申请人名称"].map(
        lambda x: "是" if any(keyword in x for keyword in HEAD_COMPANY_KEYWORDS) else "否"
    )
    grouped["是否广东样本城市"] = grouped["申请人城市"].map(
        lambda x: "是" if x in SUPPLEMENT_CITIES else "否"
    )
    grouped["主体类型判断"] = grouped["主导申请人名称"].map(infer_subject_type)
    grouped["推荐补录优先级"] = grouped.apply(score_supplement_priority, axis=1)
    grouped["补录建议"] = grouped["主体类型判断"].map(
        {
            "企业": "建议补录进企业主表",
            "高校/科研机构": "建议单独建产学研合作主体库",
            "其他组织": "建议人工判断是否纳入",
        }
    )

    grouped = grouped.sort_values(
        by=["推荐补录优先级", "专利数", "IPC主分类号数"],
        ascending=[True, False, False],
    )
    return grouped[
        [
            "主导申请人名称",
            "统一社会信用代码",
            "申请人城市",
            "当前权利人",
            "专利数",
            "IPC主分类号数",
            "首次申请年份",
            "最近申请年份",
            "主体类型判断",
            "是否广东样本城市",
            "是否头部关键词命中",
            "推荐补录优先级",
            "补录建议",
        ]
    ]


def infer_subject_type(name: str) -> str:
    if any(keyword in name for keyword in ["大学", "学院", "研究院", "实验室", "研究所", "科学院"]):
        return "高校/科研机构"
    if any(keyword in name for keyword in ["有限公司", "公司", "股份"]):
        return "企业"
    return "其他组织"


def score_supplement_priority(row: pd.Series) -> str:
    if row["主体类型判断"] != "企业":
        return "P3-非企业主体"
    if row["是否头部关键词命中"] == "是" and row["专利数"] >= 5:
        return "P1-立即补录"
    if row["是否广东样本城市"] == "是" and row["专利数"] >= 3:
        return "P1-立即补录"
    if row["专利数"] >= 10:
        return "P2-优先补录"
    return "P3-候选观察"


def export_results(
    enterprise: pd.DataFrame,
    mapping: pd.DataFrame,
    matched_df: pd.DataFrame,
    review_df: pd.DataFrame,
    portrait_df: pd.DataFrame,
    patent_enterprise_df: pd.DataFrame,
    upstream_candidate_df: pd.DataFrame,
    integrated_chain_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    supplement_df: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    enterprise_export = enterprise.drop(columns=["标准名归一化", "简称归一化"])
    mapping_export = mapping.drop(columns=["归一化名称"])

    with pd.ExcelWriter(OUTPUT_WORKBOOK, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="结果概览")
        enterprise_export.to_excel(writer, index=False, sheet_name="企业主表")
        mapping_export.to_excel(writer, index=False, sheet_name="企业名称映射表")
        matched_df.to_excel(writer, index=False, sheet_name="企业-专利匹配表")
        review_df.to_excel(writer, index=False, sheet_name="人工核验池")
        patent_enterprise_df.to_excel(writer, index=False, sheet_name="有专利企业清单")
        upstream_candidate_df.to_excel(writer, index=False, sheet_name="上游候选企业")
        integrated_chain_df.to_excel(writer, index=False, sheet_name="产业链整合清单")
        portrait_df.to_excel(writer, index=False, sheet_name="样本企业画像表")
        supplement_df.to_excel(writer, index=False, sheet_name="头部主体补录清单")

    enterprise_export.to_csv(OUTPUT_DIR / "企业主表.csv", index=False)
    mapping_export.to_csv(OUTPUT_DIR / "企业名称映射表.csv", index=False)
    matched_df.to_csv(OUTPUT_DIR / "企业-专利匹配表.csv", index=False)
    review_df.to_csv(OUTPUT_DIR / "人工核验池.csv", index=False)
    patent_enterprise_df.to_csv(OUTPUT_DIR / "有专利企业清单.csv", index=False)
    upstream_candidate_df.to_csv(OUTPUT_DIR / "上游候选企业.csv", index=False)
    integrated_chain_df.to_csv(OUTPUT_DIR / "产业链整合清单.csv", index=False)
    portrait_df.to_csv(OUTPUT_DIR / "样本企业画像表.csv", index=False)
    supplement_df.to_csv(OUTPUT_DIR / "头部主体补录清单.csv", index=False)


def main() -> None:
    base_enterprise = load_enterprises()
    supplement = load_supplement_enterprises()
    enterprise = combine_enterprise_sources(base_enterprise, supplement)
    patents = load_patents()
    mapping = build_name_mapping(enterprise)
    mapping = add_patent_aliases(mapping, patents, enterprise)
    matched_df, review_df, mapping = build_match_table(enterprise, mapping, patents)
    sample_df = build_sample(enterprise, matched_df)
    portrait_df = build_portrait(sample_df, matched_df)
    patent_enterprise_df = build_patent_enterprise_list(enterprise, matched_df)
    upstream_candidate_df = build_upstream_candidates(enterprise)
    integrated_chain_df = build_integrated_chain_list(patent_enterprise_df, upstream_candidate_df)
    summary_df = build_summary(enterprise, patents, matched_df, review_df, sample_df)
    supplement_df = build_supplement_list(enterprise, patents)
    export_results(
        enterprise,
        mapping,
        matched_df,
        review_df,
        portrait_df,
        patent_enterprise_df,
        upstream_candidate_df,
        integrated_chain_df,
        summary_df,
        supplement_df,
    )


if __name__ == "__main__":
    main()
