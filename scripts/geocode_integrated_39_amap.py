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
INTEGRATED_FILE = ROOT / "outputs" / "low_altitude_pipeline" / "产业链整合清单.csv"
ENTERPRISE_FILE = ROOT / "outputs" / "low_altitude_pipeline" / "企业主表.csv"
OUTPUT_DIR = ROOT / "outputs" / "geocode_results"
OUTPUT_CSV = OUTPUT_DIR / "产业链39家企业坐标表.csv"
OUTPUT_XLSX = OUTPUT_DIR / "产业链39家企业坐标表.xlsx"
GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


def clean_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        parts = [clean_value(item) for item in value]
        return ";".join(part for part in parts if part)
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

    integrated = pd.read_csv(INTEGRATED_FILE)
    enterprise = pd.read_csv(ENTERPRISE_FILE)[["统一社会信用代码", "注册地址", "所属城市"]]
    df = integrated.merge(enterprise, on="统一社会信用代码", how="left", suffixes=("", "_主表"))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cache: dict[tuple[str, str], dict] = {}
    rows = []
    for _, row in df.iterrows():
        address = clean_value(row["注册地址"])
        city = clean_value(row["所属城市"])
        key = (address, city)

        result = cache.get(key)
        if result is None:
            result = request_geocode(api_key, address, city)
            cache[key] = result
            time.sleep(0.08)

        geocodes = result.get("geocodes", []) if isinstance(result, dict) else []
        first = geocodes[0] if geocodes else {}
        location = clean_value(first.get("location"))
        lng = ""
        lat = ""
        if location and "," in location:
            lng, lat = location.split(",", 1)

        rows.append(
            {
                "公司名称": clean_value(row["公司名称"]),
                "统一社会信用代码": clean_value(row["统一社会信用代码"]),
                "整合后产业链环节": clean_value(row["整合后产业链环节"]),
                "是否有专利": clean_value(row["是否有专利"]),
                "注册地址": address,
                "企业表所属城市": city,
                "高德返回格式化地址": clean_value(first.get("formatted_address")),
                "高德返回省": clean_value(first.get("province")),
                "高德返回市": clean_value(first.get("city")),
                "高德返回区县": clean_value(first.get("district")),
                "adcode": clean_value(first.get("adcode")),
                "经度": lng,
                "纬度": lat,
                "level": clean_value(first.get("level")),
                "高德状态": clean_value(result.get("status")),
                "高德信息": clean_value(result.get("info")),
                "返回条数": len(geocodes),
            }
        )

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUTPUT_CSV, index=False)
    out_df.to_excel(OUTPUT_XLSX, index=False)
    matched = int(((out_df["经度"] != "") & (out_df["纬度"] != "")).sum())
    print(f"Output: {OUTPUT_CSV}")
    print(f"Matched {matched} / {len(out_df)} addresses")


if __name__ == "__main__":
    main()
