from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
MODEL_DIR = ROOT / "outputs" / "model_results"
DELIVER_DIR = ROOT / "outputs" / "final_delivery"

PRED_FILE = MODEL_DIR / "xgboost_fusion_predictions.csv"
TOP20_FILE = MODEL_DIR / "top20_xgboost_fusion_recommendations.csv"
FINAL_CSV = DELIVER_DIR / "XGBoost融合白名单推荐表.csv"
FINAL_XLSX = DELIVER_DIR / "XGBoost融合白名单推荐表.xlsx"


def main() -> None:
    DELIVER_DIR.mkdir(parents=True, exist_ok=True)
    top20 = pd.read_csv(TOP20_FILE, encoding="utf-8-sig")
    pred = pd.read_csv(PRED_FILE, encoding="utf-8-sig")

    top20.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    top20.to_excel(FINAL_XLSX, index=False)

    print(f"Saved final csv to: {FINAL_CSV}")
    print(f"Saved final xlsx to: {FINAL_XLSX}")
    print(f"All scored companies: {len(pred)}")
    print(f"Top recommendations: {len(top20)}")


if __name__ == "__main__":
    main()
