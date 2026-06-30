from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
INPUT_FILE = ROOT / "outputs" / "geocode_results" / "产业链39家企业坐标表.csv"
OUTPUT_CSV = ROOT / "outputs" / "geocode_results" / "产业链39家企业坐标表.csv"
OUTPUT_XLSX = ROOT / "outputs" / "geocode_results" / "产业链39家企业坐标表.xlsx"
GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


def clean_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        return ";".join(clean_value(item) for item in value if clean_value(item))
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def request_geocode(api_key: str, address: str, city: str) -> dict:
    params = {
        "key": api_key,
        "address": address,
        "city": city,
        "output": "JSON",
    }
    url = f"{GEOCODE_URL}?{urllib.parse.urlencode(params)}"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, timeout=20, context=ssl_context) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    api_key = os.getenv("AMAP_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing AMAP_API_KEY environment variable.")

    df = pd.read_csv(INPUT_FILE)
    for column in [
        "高德返回格式化地址",
        "高德返回省",
        "高德返回市",
        "高德返回区县",
        "adcode",
        "经度",
        "纬度",
        "level",
        "高德状态",
        "高德信息",
    ]:
        if column in df.columns:
            df[column] = df[column].astype("string")
    retry_mask = df["经度"].isna() | df["纬度"].isna() | (df["经度"].astype(str) == "") | (df["纬度"].astype(str) == "")
    retry_df = df[retry_mask].copy()

    print(f"Retrying {len(retry_df)} failed rows")

    for idx, row in retry_df.iterrows():
        address = clean_value(row["注册地址"])
        city = clean_value(row["企业表所属城市"])
        result = request_geocode(api_key, address, city)
        geocodes = result.get("geocodes", []) if isinstance(result, dict) else []
        first = geocodes[0] if geocodes else {}
        location = clean_value(first.get("location"))
        lng = ""
        lat = ""
        if location and "," in location:
            lng, lat = location.split(",", 1)

        df.at[idx, "高德返回格式化地址"] = clean_value(first.get("formatted_address"))
        df.at[idx, "高德返回省"] = clean_value(first.get("province"))
        df.at[idx, "高德返回市"] = clean_value(first.get("city"))
        df.at[idx, "高德返回区县"] = clean_value(first.get("district"))
        df.at[idx, "adcode"] = clean_value(first.get("adcode"))
        df.at[idx, "经度"] = lng
        df.at[idx, "纬度"] = lat
        df.at[idx, "level"] = clean_value(first.get("level"))
        df.at[idx, "高德状态"] = clean_value(result.get("status"))
        df.at[idx, "高德信息"] = clean_value(result.get("info"))
        df.at[idx, "返回条数"] = len(geocodes)

        print(row["公司名称"], df.at[idx, "高德状态"], df.at[idx, "高德信息"], lng, lat)
        time.sleep(0.6)

    df.to_csv(OUTPUT_CSV, index=False)
    df.to_excel(OUTPUT_XLSX, index=False)
    matched = int(((df["经度"].notna()) & (df["纬度"].notna()) & (df["经度"].astype(str) != "") & (df["纬度"].astype(str) != "")).sum())
    print(f"Matched {matched} / {len(df)} addresses after retry")


if __name__ == "__main__":
    main()
